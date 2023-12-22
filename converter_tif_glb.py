import numpy as np
import tifffile
import pyvista as pv
import argparse
import trimesh
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image
import json

def float_list(input_str):
    try:
        return [float(val.strip()) for val in input_str.split(',')]
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid float list: '{input_str}'")

def transparency(value, low, mid, upp) :
	if value < low:
		return 1.0
	elif value >= low and value <= mid :
		return 0.75
	elif value >= upp :
		return 0.5
	else:
		return 1.0 # fully transparent

def opacity_function(value):
    return 1.0 - value

def create_material(color = [20, 20, 230, 250]) :
	# RGBA (for color blue-greyish and 216 for 85% transparency)
	texture = Image.new('RGBA', (1, 1), tuple(color))
	pbr_material = trimesh.visual.material.PBRMaterial(
		metallicFactor=0,
		roughnessFactor=1,
		baseColorTexture=texture,
		alphaMode="BLEND",
	)
	return pbr_material

def tif_to_glb(
		input_tif_filename, output_glb_filename, lower_threshold=100,
		middle_threshold=350, upper_threshold=900,
		horizontal_spacing=1, vertical_spacing=1,
		depth_spacing=1, contour_values = [0.1,0.3,1.0],
	):
	# Read the 3D TIF file as a numpy array
	volume_data = tifffile.imread(input_tif_filename)
	
	# Apply the transparency function to the volume_data
	#max_value = np.max(volume_data)
	vectorized_func = np.vectorize(transparency, otypes=[np.float32], excluded=[1, 2])
	transparency_data = vectorized_func(volume_data, low=lower_threshold, mid=middle_threshold, upp=upper_threshold)
	
	# Normalize the volume_data
	normalized_data = (volume_data - volume_data.min()) / (volume_data.max() - volume_data.min())
	
	# Create a pyvista grid from the binary volume
	print("Create a pyvista grid from the binary volume")
	grid = pv.UniformGrid()
	grid.SetDimensions(volume_data.shape)
	grid.SetSpacing(depth_spacing, vertical_spacing, horizontal_spacing) # (z, x, y)
	grid.SetOrigin(0, 0, 0)

	# Set the volume data and the transparency data
	print("Set the volume data and the transparency data")
	grid.point_data.set_array(normalized_data.flatten(order='F'), 'values')
	grid.point_data.set_array(transparency_data.flatten(order='F'), 'transparency')
	grid.set_active_scalars("values")
	
	# Create a mesh using PyVista
	print("Create meshes using PyVista")
	all_contours = []
	for value in contour_values :
		print("Adding contour value: {}".format(value))
		all_contours.append(grid.contour([value]))
	
	""" DEPRECATED NOW
	# Prepare a colormap with desired transparency values
	color_array = plt.cm.Greys(np.linspace(0, 1, num=256))
	transparency_values = np.array([opacity_function(val) for val in np.linspace(0, 1, num=256)])
	color_array[:, 3] = transparency_values
	cmap_transparent = mcolors.ListedColormap(color_array)
	
	# Create the PyVista Plotter
	
	print("Create the PyVista Plotter")
	plotter = pv.Plotter()
	
	# Add the contours to the plotter
	print("Add the contours to the plotter")
	#plotter.add_mesh(contours1, scalars='transparency', clim=[0, 1], cmap=cmap_transparent)
	plotter.add_mesh(contours2, scalars='transparency', clim=[0, 1], cmap=cmap_transparent)
	#plotter.add_mesh(contours3, scalars='transparency', clim=[0, 1], cmap=cmap_transparent)
	plotter.set_background(color='lightblue')
	plotter.show()
	"""
	
	# Saving to object
	print("Saving to object and loading in Trimesh")
	meshes = []
	for i, contour in enumerate(all_contours) :
		mesh_name = "mesh{}.stl".format(i)
		contour.save(mesh_name)
		meshes.append(trimesh.load_mesh(mesh_name))
	
	darkgrey_mat = create_material([50, 50, 50, 100])
	lightblue_mat = create_material([20, 100, 200, 150])
	lightgrey_mat = create_material([175, 175, 175, 150]) # now yellow
	
	scene = trimesh.Scene()
	meshes[0].visual = trimesh.visual.TextureVisuals(material=lightgrey_mat) # outermost
	for i, mesh in enumerate(meshes[1:]) :
		mesh.visual = trimesh.visual.TextureVisuals(material=lightblue_mat) # all inner layers
	
	for i, mesh in enumerate(meshes) :
		name = "mesh{}".format(i)
		scene.add_geometry(mesh, node_name=name)

	scene.export(output_glb_filename)


def main():
	parser = argparse.ArgumentParser(description='Convert a 3D TIF file to a GLB file.')

	parser.add_argument('-i', '--input', type=str, required=True, help='Input 3D TIF file.')
	parser.add_argument('-o', '--output', type=str, required=True, help='Output GLB file.')
	parser.add_argument('-lt', '--lower-threshold', type=int, default=100, help='Threshold for full transparency (noise signal).')
	parser.add_argument('-mt', '--middle-threshold', type=int, default=350, help='Threshold for high transparency (outer layer of chromosomes, low intensity signal).')
	parser.add_argument('-ut', '--upper-threshold', type=int, default=900, help='Threshold for low transparency (core of chromosomes, high intensity signal).')
	parser.add_argument('-hs', '--horizontal-spacing', type=int, default=1, help='Spacing of x pixels (default: 1).')
	parser.add_argument('-vs', '--vertical-spacing', type=int, default=1, help='Spacing of y pixels (default: 1).')
	parser.add_argument('-ds', '--depth-spacing', type=int, default=1, help='Spacing of z pixels (e.g.: slice thickness) (default: 1).')
	parser.add_argument('-c', '--contours', type=float_list, default=[0.1, 0.3, 1.0], help='List of float values (comma-separated). Default: [0.1, 0.3, 1.0].')

	args = parser.parse_args()
	
	print("Arguments parsed:")
	print("- Thresholds: {}".format([args.lower_threshold, args.middle_threshold, args.upper_threshold]))
	print("- Contour values: {}".format(args.contours))

	tif_to_glb(
		args.input, args.output,
		lower_threshold=args.lower_threshold,
		middle_threshold=args.middle_threshold,
		upper_threshold=args.upper_threshold,
		horizontal_spacing=args.horizontal_spacing,
		vertical_spacing=args.vertical_spacing,
		depth_spacing=args.depth_spacing,
		contour_values=args.contours
	)

if __name__ == "__main__":
    main()