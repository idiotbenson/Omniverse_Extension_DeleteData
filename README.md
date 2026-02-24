# Omniverse_Extension_DeleteData

This is an Omniverse Kit Python UI extension that focuses on cleaning and optimizing USD scenes, with custom string management and mesh optimization.
Basic Info
Package name: BwnsonDelDataExtension
Version: 0.1.0
Module: deldata.benson_python_ui_extension
Dependency: omni.kit.uiapp
Main Features

1. Custom String Management
Search Custom String – Search for custom string attributes by name
Search in selected prims or the whole scene
Auto-selects matching prims
Add Custom String to Selected – Add custom string attributes to selected prims
Recursively processes children
Supports Mesh, Xform, etc.
2. Cleanup Tools
Search Empty Custom Strings – Find and remove empty custom string attributes on Mesh and Xform prims
Delete Inactive Prims – Remove inactive Mesh and Xform prims
Works on both stage and layers
Performs search and delete in phases
Delete Material Deltas – Remove inactive Material overrides
Cleans stage and layer stack specs
3. Mesh Optimization
Make Selected Single-Sided – Set selected meshes to single-sided (singleSided=True)
Processes Xform containers recursively
4. Utilities
Debug Report – Outputs debug reports for Inactive Prim Cleaner and Material Delta Cleaner to the console
Architecture
Class	Purpose
UnicodeHelper	Safe string handling for Unicode
USDOperations	USD operations (stage, traversal, layers)
CustomStringCleaner	Removes empty custom string attributes
MaterialDeltaCleaner	Removes inactive Material deltas
InactivePrimCleaner	Removes inactive Mesh/Xform prims
MyExtension	Main extension class and UI wiring
UI
The extension opens a “USD Cleaner” window (about 280×480 px) with:
Status label for operation results
Buttons and inputs for each feature
Sections for different tools
Use Cases
Cleaning redundant or invalid data in USD scenes
Removing inactive prims and material deltas
Managing and searching custom string attributes
Setting meshes to single-sided for rendering optimization
