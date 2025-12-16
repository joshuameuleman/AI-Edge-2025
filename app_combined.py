"""
Combined Gradio app with three features:
 - Text -> 3D (TRELLIS text pipeline)
 - Image -> 3D (TRELLIS image pipeline)
 - GLB -> STEP converter

This file initializes both pipelines and reuses existing helper functions
from `app_text.py` and `app.py` by setting their `pipeline` globals so we
don't duplicate generation code. It also exposes a simple GLB->STEP tab
using `glb_to_step.py`.

Run this script inside the container to start a single app with all
features. It binds to 0.0.0.0 and uses port 7860 by default.
"""
import os
import sys
import gradio as gr
from pathlib import Path

# Workaround: some versions of `gradio_client.utils` assume JSON schema objects
# are dict-like and will error if a boolean (True/False) appears (valid in
# JSON Schema as `additionalProperties: false`). Patch the utility functions at
# import time so the server doesn't crash with "argument of type 'bool' is not iterable".
try:
    import gradio_client.utils as _gc_utils

    if hasattr(_gc_utils, "_json_schema_to_python_type"):
        _orig__json_schema_to_python_type = _gc_utils._json_schema_to_python_type

        def _patched__json_schema_to_python_type(schema, defs=None):
            if isinstance(schema, bool):
                return "bool"
            return _orig__json_schema_to_python_type(schema, defs)

        _gc_utils._json_schema_to_python_type = _patched__json_schema_to_python_type

    if hasattr(_gc_utils, "get_type"):
        _orig_get_type = _gc_utils.get_type

        def _patched_get_type(schema):
            if isinstance(schema, bool):
                return "bool"
            return _orig_get_type(schema)

        _gc_utils.get_type = _patched_get_type
except Exception:
    # If the gradio client API isn't present or the patch fails, don't stop startup;
    # the original error will surface and can be investigated. This avoids raising
    # during import in environments without gradio_client available.
    pass

# Reuse the existing modules' helper functions where possible
# Ensure the `TRELLIS` package directory is on `sys.path` when running
# this script from the repository root so `import app_text` / `trellis` works.
HERE = os.path.dirname(__file__)
TRELLIS_DIR = os.path.join(HERE, "TRELLIS")
if TRELLIS_DIR not in sys.path:
    sys.path.insert(0, TRELLIS_DIR)

import app_text
import app
from glb_to_step import glb_to_step


# Initialize pipelines and assign into modules so their functions work
def init_pipelines():
    # Initialize text pipeline
    try:
        from trellis.pipelines import TrellisTextTo3DPipeline
        app_text.pipeline = TrellisTextTo3DPipeline.from_pretrained("microsoft/TRELLIS-text-xlarge")
        app_text.pipeline.cuda()
    except Exception as e:
        print("Warning: failed to init text pipeline:", e)

    # Initialize image pipeline
    try:
        from trellis.pipelines import TrellisImageTo3DPipeline
        app.pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
        app.pipeline.cuda()
    except Exception as e:
        print("Warning: failed to init image pipeline:", e)


def make_ui():
    with gr.Blocks() as demo:
        gr.Markdown("""
        ## TRELLIS Unified Demo
        Choose a tab: generate 3D from text, from an image (single or multi-view),
        or convert an existing `.glb` to STEP for download.
        """)

        with gr.Tabs():
            with gr.TabItem("Text → 3D"):
                # replicate the key inputs from app_text
                text_prompt = gr.Textbox(label="Text Prompt", lines=4)
                seed = gr.Slider(0, 2**31-1, label="Seed", value=0, step=1)
                randomize_seed = gr.Checkbox(label="Randomize Seed", value=True)
                ss_guidance_strength = gr.Slider(0.0, 10.0, label="SS Guidance", value=7.5)
                ss_sampling_steps = gr.Slider(1, 50, label="SS Steps", value=25)
                slat_guidance_strength = gr.Slider(0.0, 10.0, label="SLAT Guidance", value=7.5)
                slat_sampling_steps = gr.Slider(1, 50, label="SLAT Steps", value=25)
                # Preset selector for common profiles
                text_preset = gr.Radio(["Fast", "Balanced", "High Quality"], label="Preset", value="Balanced")

                def apply_text_preset(preset: str):
                    if preset == "Fast":
                        return 5.0, 12, 3.0, 8
                    if preset == "High Quality":
                        return 9.0, 40, 8.5, 30
                    # Balanced
                    return 7.5, 25, 7.5, 25

                text_preset.change(apply_text_preset, inputs=[text_preset], outputs=[ss_guidance_strength, ss_sampling_steps, slat_guidance_strength, slat_sampling_steps])
                generate_text = gr.Button("Generate from text")
                text_video = gr.Video(label="Generated 3D (text)")
                text_download = gr.File(label="Download GLB (text)")

                def _gen_text(randomize, s):
                    return app_text.get_seed(randomize, s)

                # After generating, also auto-extract a GLB into the session tmp dir
                def _auto_extract_text_glb(state, req=None):
                    try:
                        # Use reasonable defaults for simplify/texture_size
                        glb_path, msg = app_text.extract_glb(state, 0.95, 1024, req)
                        return glb_path
                    except Exception:
                        return None

                generate_text.click(_gen_text, inputs=[randomize_seed, seed], outputs=[seed]).then(
                    app_text.text_to_3d,
                    inputs=[text_prompt, seed, ss_guidance_strength, ss_sampling_steps, slat_guidance_strength, slat_sampling_steps],
                    outputs=[gr.State(), text_video],
                ).then(
                    _auto_extract_text_glb,
                    inputs=[gr.State()],
                    outputs=[text_download],
                )

                # allow extraction/download after generation
                gr.Examples(examples=["a red chair", "a small wooden table"], inputs=[text_prompt])

            with gr.TabItem("Image → 3D"):
                # reuse UI from app.py
                image_prompt = gr.Image(label="Image Prompt", format="png", image_mode="RGBA", type="pil", height=300)
                multiimage_prompt = gr.Gallery(label="Multi-image Prompt", format="png", type="pil", height=300, columns=3)
                seed_i = gr.Slider(0, 2**31-1, label="Seed", value=0, step=1)
                randomize_seed_i = gr.Checkbox(label="Randomize Seed", value=True)
                ss_guidance_strength_i = gr.Slider(0.0, 10.0, label="SS Guidance", value=7.5)
                ss_sampling_steps_i = gr.Slider(1, 50, label="SS Steps", value=12)
                slat_guidance_strength_i = gr.Slider(0.0, 10.0, label="SLAT Guidance", value=3.0)
                slat_sampling_steps_i = gr.Slider(1, 50, label="SLAT Steps", value=12)
                multiimage_algo = gr.Radio(["stochastic", "multidiffusion"], label="Multi-image Algorithm", value="stochastic")
                # Preset selector for image pipeline
                image_preset = gr.Radio(["Fast", "Balanced", "High Quality"], label="Preset", value="Balanced")

                def apply_image_preset(preset: str):
                    if preset == "Fast":
                        return 5.0, 12, 3.0, 8
                    if preset == "High Quality":
                        # For image pipelines we favor more SLAT steps for detail
                        return 8.5, 40, 6.0, 30
                    # Balanced (image defaults tuned for speed/quality)
                    return 7.5, 12, 3.0, 12

                image_preset.change(apply_image_preset, inputs=[image_preset], outputs=[ss_guidance_strength_i, ss_sampling_steps_i, slat_guidance_strength_i, slat_sampling_steps_i])
                generate_img = gr.Button("Generate from image")
                img_video = gr.Video(label="Generated 3D (image)")
                img_download = gr.File(label="Download GLB (image)")
                img_stl_download = gr.File(label="Download STL (image)")
                image_state = gr.State()

                def _gen_image(randomize, s):
                    return app.get_seed(randomize, s)

                def _auto_extract_image_glb(state, req=None):
                    try:
                        glb_path, _ = app.extract_glb(state, 0.95, 1024, req)
                        return glb_path
                    except Exception:
                        return None

                generate_img.click(_gen_image, inputs=[randomize_seed_i, seed_i], outputs=[seed_i]).then(
                    app.image_to_3d,
                    inputs=[image_prompt, multiimage_prompt, gr.State(False), seed_i, ss_guidance_strength_i, ss_sampling_steps_i, slat_guidance_strength_i, slat_sampling_steps_i, multiimage_algo],
                    outputs=[image_state, img_video],
                ).then(
                    app.extract_stl,
                    inputs=[image_state],
                    outputs=[gr.State(), img_stl_download],
                ).then(
                    _auto_extract_image_glb,
                    inputs=[image_state],
                    outputs=[img_download],
                )

            with gr.TabItem("GLB → STEP"):
                glb_file = gr.File(label='Upload .glb file')
                use_latest_btn = gr.Button('Use Latest Generated GLB')
                latest_state = gr.State(value=None)
                convert_btn = gr.Button('Convert to STEP')
                step_download = gr.File(label='Download STEP')
                status = gr.Textbox(label='Status')

                def find_latest_glb(req=None):
                    # Look for the generated `sample.glb` in the session tmp dir used by `app_text`.
                    # Accepts an optional `gr.Request` (recommended) but also falls
                    # back to scanning `app_text.TMP_DIR` for any recent `sample.glb`.
                    try:
                        if req is not None and hasattr(req, "session_hash"):
                            user_dir = os.path.join(app_text.TMP_DIR, str(req.session_hash))
                            p = os.path.join(user_dir, 'sample.glb')
                            if os.path.exists(p):
                                return p, "Found latest generated GLB"
                            return None, "No generated GLB found for this session"

                        # Fallback: find the most recent `sample.glb` under TMP_DIR
                        try:
                            tmp_path = Path(app_text.TMP_DIR)
                            if tmp_path.is_dir():
                                glbs = list(tmp_path.rglob('sample.glb'))
                                if glbs:
                                    latest = max(glbs, key=lambda p: p.stat().st_mtime)
                                    return str(latest), f"Found latest generated GLB: {latest}"
                        except Exception:
                            pass

                        return None, "No generated GLB found"
                    except Exception as e:
                        return None, f"Error locating latest GLB: {e}"

                def _convert_file(file_obj, latest_path):
                    inp_path = None
                    if file_obj is not None:
                        inp_path = file_obj.name
                    elif latest_path:
                        inp_path = latest_path
                    else:
                        return None, "No GLB provided or found"

                    out = Path(inp_path).with_suffix('.step')
                    try:
                        step_path = glb_to_step(str(inp_path), str(out))
                        return step_path, "Conversion successful"
                    except Exception as e:
                        stl = Path(inp_path).with_suffix('.stl')
                        if stl.exists():
                            return str(stl), f"STEP conversion failed: {e}. Provided STL instead."
                        return None, f"Conversion failed: {e}"

                # Wire buttons: find latest fills the `latest_state`, convert uses uploaded file or latest_state
                # Call without `gr.Request()` to avoid component config errors; the function will fall back to scanning TMP_DIR.
                use_latest_btn.click(find_latest_glb, inputs=[], outputs=[latest_state, status])
                convert_btn.click(_convert_file, inputs=[glb_file, latest_state], outputs=[step_download, status])

        return demo


if __name__ == '__main__':
    init_pipelines()
    demo = make_ui()
    # Gradio 4.x uses the `queue()` method to enable request queuing before launch.
    # Avoid passing unsupported `enable_queue` kwarg to `launch`.
    demo.queue()
    # When running inside some container/orchestrated environments Gradio
    # may require a shareable link to be created for the app to be reachable.
    # Set `share=True` here so the app starts reliably inside the container.
    demo.launch(server_name='0.0.0.0', server_port=7860, share=True)
