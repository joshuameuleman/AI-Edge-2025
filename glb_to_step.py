#!/usr/bin/env python3
"""
Convert a GLB/GLTF mesh file to a STEP file.

This script attempts to convert a triangulated mesh (GLB/GLTF) into a
STEP (CAD) file using pythonocc-core (OCCT bindings). If `pythonocc-core`
is not available in the environment, the script will raise a clear error
explaining how to install the missing dependency. As a fallback the tool
exports an intermediate STL so users can convert externally.

Note: Converting arbitrary triangle meshes to valid CAD solids is
non-trivial and may fail for non-manifold or open meshes. The script
performs a best-effort sewing of triangle faces into a shell and writes
the STEP file. For higher-quality results, preprocess the mesh in a CAD
tool (FreeCAD) or repair it before conversion.
"""
import sys
import os
import tempfile
from pathlib import Path

import trimesh


def _repair_mesh(stl_path: str) -> str:
    """Attempt to repair the mesh at `stl_path` and write a repaired STL next to it.

    Returns the path to the repaired STL (may be the same as input if repair not needed
    or repair tools unavailable).
    """
    try:
        mesh = trimesh.load(stl_path, force='mesh')
    except Exception:
        return stl_path

    repaired_path = str(Path(stl_path).with_suffix('.repaired.stl'))

    # Quick fixes using trimesh
    try:
        if not mesh.is_watertight:
            try:
                mesh = mesh.copy()
                trimesh.repair.fill_holes(mesh)
            except Exception:
                pass

        try:
            trimesh.repair.fix_normals(mesh)
        except Exception:
            pass

        # Remove degenerate faces and small components
        try:
            mesh.remove_degenerate_faces()
        except Exception:
            pass

        # If pymeshfix is available, use it for more aggressive hole filling
        try:
            import pymeshfix

            mf = pymeshfix.MeshFix(mesh)
            mf.repair()
            mesh = mf.mesh
        except Exception:
            # pymeshfix may not be installed; that's OK — trimesh repairs may suffice
            pass

        # Export repaired mesh
        mesh.export(repaired_path)
        return repaired_path
    except Exception:
        return stl_path


def glb_to_step(glb_path: str, step_path: str = None) -> str:
    """Convert `glb_path` (GLB/GLTF) to STEP file at `step_path`.

    Returns the path to the written STEP file.
    """
    glb_path = str(glb_path)
    if step_path is None:
        step_path = str(Path(glb_path).with_suffix('.step'))

    mesh = trimesh.load(glb_path, force='mesh')
    if mesh.is_empty:
        raise ValueError(f"Loaded mesh is empty: {glb_path}")

    # Export an STL next to the GLB so users can download it regardless of STEP success.
    stl_path = str(Path(glb_path).with_suffix('.stl'))
    mesh.export(stl_path)

    # Attempt to repair the STL before conversion. This will write
    # `<name>.repaired.stl` if repair succeeds and return that path.
    repaired_stl = _repair_mesh(stl_path)
    if repaired_stl != stl_path:
        # prefer repaired STL for conversion
        stl_path = repaired_stl

    # Try to import pythonocc and perform mesh->STEP conversion.
    try:
        # Core OCC imports
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCC.Core.IFSelect import IFSelect_RetDone
    except Exception as exc:  # pragma: no cover - environment dependent
        # If pythonocc-core is not available, attempt to use FreeCAD headlessly
        # to convert the STL we exported above into a STEP file. If FreeCAD is
        # not present, raise a clear error but do not remove the STL so the
        # user can download it and convert locally.
        import shutil
        import subprocess

        freecad_bin = shutil.which("FreeCADCmd") or shutil.which("freecadcmd") or shutil.which("freecad")
        if freecad_bin:
            # Prepare a small FreeCAD python script that imports the STL and
            # exports a STEP. Use a temporary on-disk script to avoid shell escaping issues.
            fc_script_fd, fc_script_path = tempfile.mkstemp(suffix='.py')
            os.close(fc_script_fd)
            # Use Mesh and MeshPart to convert the mesh into a Part shape,
            # then attempt to create a solid from the shell. This is more
            # robust than inserting into a document and exporting directly.
            fc_script_contents = f"""
import Mesh
import MeshPart
import Part
import FreeCAD
try:
    m = Mesh.Mesh(r'{stl_path}')
    shape = MeshPart.meshToShape(m)
    # Attempt to create a shell and solid if possible
    try:
        faces = list(shape.Faces)
        shell = Part.Shell(faces)
        solid = Part.Solid(Part.Shell(faces))
        Part.export([solid], r'{step_path}')
    except Exception:
        # Fall back to exporting the shape as-is
        Part.export([shape], r'{step_path}')
except Exception as e:
    raise SystemExit(f"FreeCAD conversion script failed: {{e}}")
"""
            with open(fc_script_path, 'w') as f:
                f.write(fc_script_contents)

            try:
                proc = subprocess.run([freecad_bin, fc_script_path], capture_output=True, text=True, timeout=300)
                if proc.returncode == 0 and os.path.exists(step_path):
                    # Keep the STL available for download and return the STEP path
                    try:
                        os.remove(fc_script_path)
                    except Exception:
                        pass
                    return step_path
                else:
                    # FreeCAD ran but failed to produce STEP
                    stderr = proc.stderr if proc is not None else ""
                    raise RuntimeError(f"FreeCAD conversion failed: exit={proc.returncode} stderr={stderr}")
            except Exception:
                # If FreeCAD invocation fails, surface a clear error but keep the STL
                raise RuntimeError(
                    "STEP conversion failed. FreeCAD was detected but conversion failed. "
                    "The intermediate STL has been written to: " + stl_path
                ) from exc
        else:
            # No pythonocc and no FreeCAD; inform user but keep STL for manual conversion.
            raise RuntimeError(
                "pythonocc-core is required to convert to STEP in this environment, or install FreeCAD. "
                "The intermediate STL has been written to: " + stl_path
            ) from exc

    verts = mesh.vertices
    faces = mesh.faces

    # Build a compound of triangular faces then sew them into a shell/solid.
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    sewing = BRepBuilderAPI_Sewing()

    for tri in faces:
        v0 = verts[tri[0]]
        v1 = verts[tri[1]]
        v2 = verts[tri[2]]

        p0 = gp_Pnt(float(v0[0]), float(v0[1]), float(v0[2]))
        p1 = gp_Pnt(float(v1[0]), float(v1[1]), float(v1[2]))
        p2 = gp_Pnt(float(v2[0]), float(v2[1]), float(v2[2]))

        poly = BRepBuilderAPI_MakePolygon()
        poly.Add(p0)
        poly.Add(p1)
        poly.Add(p2)
        poly.Add(p0)
        try:
            wire = poly.Wire()
            face = BRepBuilderAPI_MakeFace(wire.Wire())
            sewing.Add(face.Shape())
        except Exception:
            # Skip problematic triangles
            continue

    sewing.Perform()
    sewn_shape = sewing.SewedShape()

    writer = STEPControl_Writer()
    writer.Transfer(sewn_shape, STEPControl_AsIs)
    status = writer.Write(step_path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP writer returned status {status}")

    # We intentionally do NOT remove the STL; keep it available for download.
    return step_path


def main(argv):
    if len(argv) < 2:
        print("Usage: glb_to_step.py input.glb [output.step]")
        return 2
    inp = argv[1]
    out = argv[2] if len(argv) > 2 else None
    out = glb_to_step(inp, out)
    print("Wrote STEP:", out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
