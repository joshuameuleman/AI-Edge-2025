#!/usr/bin/env python3
"""
Simple Gradio app to upload a `.glb` file, convert it to STEP, and provide
the STEP file for download. This uses `glb_to_step.glb_to_step` under the hood.

Note: The conversion requires `pythonocc-core` to be available in the
environment. If it's not installed the app will return an informative error
and provide the intermediate STL for download instead.
"""
import gradio as gr
import tempfile
import os
from pathlib import Path

from glb_to_step import glb_to_step


def convert_upload(file_obj):
    if file_obj is None:
        return None, "No file uploaded"

    # file_obj is a tempfile-like object (Gradio provides a path)
    input_path = file_obj.name
    tmp_dir = tempfile.mkdtemp(prefix='glb2step_')
    output_step = os.path.join(tmp_dir, Path(input_path).stem + '.step')
    try:
        step_path = glb_to_step(input_path, output_step)
        return step_path, "Conversion successful"
    except Exception as e:
        # If conversion failed, provide intermediate STL if exists
        stl_path = Path(input_path).with_suffix('.stl')
        if stl_path.exists():
            return str(stl_path), f"Conversion to STEP failed: {e}. Provided STL instead."
        return None, f"Conversion failed: {e}"


with gr.Blocks() as demo:
    gr.Markdown("## GLB -> STEP converter (best-effort)")
    with gr.Row():
        inp = gr.File(label='Upload .glb file')
        out_file = gr.File(label='Download STEP (or STL fallback)')
    status = gr.Textbox(label='Status')

    convert_btn = gr.Button('Convert')
    convert_btn.click(convert_upload, inputs=[inp], outputs=[out_file, status])

if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0', server_port=7870)
