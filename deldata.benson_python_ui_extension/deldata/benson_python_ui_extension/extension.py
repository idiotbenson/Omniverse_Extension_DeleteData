import omni.ext
import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Sdf, UsdShade
from typing import Tuple, List, Optional, Set
import logging
import time
from collections import defaultdict

# Configure logging with more detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UnicodeHelper:
    """Helper class for safe Unicode string operations."""

    @staticmethod
    def safe_str(obj, fallback: str = "<encoding_error>") -> str:
        """Safely convert any object to string, handling Unicode errors."""
        if obj is None:
            return "None"

        try:
            if isinstance(obj, bytes):
                # Try different encodings for bytes
                for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                    try:
                        return obj.decode(encoding)
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                return fallback
            elif isinstance(obj, str):
                # Test if string can be encoded/decoded safely
                try:
                    obj.encode('utf-8').decode('utf-8')
                    return obj
                except (UnicodeDecodeError, UnicodeEncodeError, UnicodeError):
                    return fallback
            else:
                # For other types, convert to string and test
                str_obj = str(obj)
                try:
                    str_obj.encode('utf-8').decode('utf-8')
                    return str_obj
                except (UnicodeDecodeError, UnicodeEncodeError, UnicodeError):
                    return fallback
        except Exception:
            return fallback

    @staticmethod
    def safe_get_attr_value(attr) -> Optional[str]:
        """Safely get attribute value, handling Unicode errors."""
        try:
            value = attr.Get()
            if value is None:
                return None

            # Handle different value types safely
            if isinstance(value, bytes):
                # Try different encodings for bytes
                for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                    try:
                        decoded = value.decode(encoding)
                        # Test if it can be re-encoded safely
                        decoded.encode('utf-8')
                        return decoded
                    except (UnicodeDecodeError, UnicodeEncodeError, UnicodeError):
                        continue
                return None  # Skip if can't decode safely
            elif isinstance(value, str):
                try:
                    # Test if string can be encoded safely
                    value.encode('utf-8')
                    return value
                except (UnicodeEncodeError, UnicodeError):
                    return None  # Skip if can't encode safely
            else:
                # For other types, convert to string and test
                try:
                    str_value = str(value)
                    str_value.encode('utf-8')
                    return str_value
                except (UnicodeDecodeError, UnicodeEncodeError, UnicodeError):
                    return None
        except Exception:
            return None


class USDOperations:
    """Helper class for USD operations."""

    @staticmethod
    def get_stage() -> Optional[Usd.Stage]:
        """Get the current USD stage safely."""
        try:
            stage = omni.usd.get_context().get_stage()
            if stage:
                logger.debug(f"Successfully got USD stage: {UnicodeHelper.safe_str(stage.GetRootLayer().identifier)}")
            else:
                logger.warning("USD stage is None")
            return stage
        except Exception as e:
            logger.error(f"Failed to get USD stage: {e}")
            return None

    @staticmethod
    def get_target_prims(stage: Usd.Stage, prim_types: List[str]) -> List[Usd.Prim]:
        """Get all prims of specified types from the stage."""
        target_prims = []
        try:
            for prim in stage.TraverseAll():
                try:
                    prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                    if prim_type in prim_types:
                        target_prims.append(prim)
                except Exception:
                    # Skip prims that cause any errors
                    continue
        except Exception as e:
            logger.error(f"Error traversing stage: {e}")

        return target_prims

    @staticmethod
    def get_layers_to_check(stage: Usd.Stage) -> List:
        """Get all layers that should be checked for overrides."""
        layers_to_check = []

        try:
            # Get the session layer and edit target layer
            session_layer = stage.GetSessionLayer()
            edit_target_layer = stage.GetEditTarget().GetLayer()

            if session_layer:
                layers_to_check.append(session_layer)
                logger.debug(f"Added session layer: {UnicodeHelper.safe_str(session_layer.identifier)}")
            if edit_target_layer and edit_target_layer not in layers_to_check:
                layers_to_check.append(edit_target_layer)
                logger.debug(f"Added edit target layer: {UnicodeHelper.safe_str(edit_target_layer.identifier)}")

            # Also check all layers in the layer stack
            layer_stack = stage.GetLayerStack()
            for layer in layer_stack:
                if layer and layer not in layers_to_check:
                    layers_to_check.append(layer)
                    logger.debug(f"Added layer from stack: {UnicodeHelper.safe_str(layer.identifier)}")

            logger.info(f"Total layers to check: {len(layers_to_check)}")

        except Exception as e:
            logger.error(f"Error getting layers: {e}")

        return layers_to_check


class CustomStringCleaner:
    """Handles removal of empty custom string attributes."""

    def __init__(self):
        self.found_count = 0
        self.removed_count = 0

    def process_prim(self, prim: Usd.Prim) -> None:
        """Process a single prim for empty custom string attributes."""
        try:
            prim_path = UnicodeHelper.safe_str(prim.GetPath())
            prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
            logger.debug(f"Checking {prim_type}: {prim_path}")

            # Get all custom attributes on this prim
            try:
                custom_attrs = prim.GetAttributes()
            except Exception:
                logger.warning(f"Error getting attributes for {prim_path}, skipping prim")
                return

            empty_custom_strings = self._find_empty_custom_strings(custom_attrs)
            if empty_custom_strings:
                logger.info(f"Found {len(empty_custom_strings)} empty custom strings in {prim_type}: {prim_path}")
                self._remove_empty_attributes(prim, empty_custom_strings, prim_type, prim_path)

        except Exception as e:
            logger.error(f"Error processing prim {UnicodeHelper.safe_str(prim.GetPath())}: {UnicodeHelper.safe_str(e)}")

    def _find_empty_custom_strings(self, custom_attrs) -> List[str]:
        """Find all empty custom string attributes."""
        empty_custom_strings = []

        for attr in custom_attrs:
            try:
                # Check if it's a custom string attribute
                if not attr.IsCustom():
                    continue

                type_name = UnicodeHelper.safe_str(attr.GetTypeName())
                if type_name != "string":
                    continue

                # Safely get attribute name and value
                attr_name = UnicodeHelper.safe_str(attr.GetName())
                if attr_name == "<encoding_error>":
                    logger.warning("Skipping attribute with unreadable name")
                    continue

                value = UnicodeHelper.safe_get_attr_value(attr)
                if value is None:
                    logger.warning(f"Skipping attribute {attr_name} with unreadable value")
                    continue

                # Check if the value is empty string
                if value == "":
                    empty_custom_strings.append(attr_name)
                    self.found_count += 1
                    logger.debug(f"Found empty custom string: {attr_name}")

            except Exception as e:
                logger.error(f"Error processing attribute: {UnicodeHelper.safe_str(e)}")
                continue

        return empty_custom_strings

    def _remove_empty_attributes(self, prim: Usd.Prim, attr_names: List[str],
                               prim_type: str, prim_path: str) -> None:
        """Remove empty custom string attributes from a prim."""
        for attr_name in attr_names:
            try:
                # Get the attribute and remove it
                attr = prim.GetAttribute(attr_name)
                if attr:
                    # Use USD edit target to remove the attribute
                    with Sdf.ChangeBlock():
                        prim.RemoveProperty(attr_name)
                    self.removed_count += 1
                    logger.debug(f"Removed empty custom string: {attr_name} from {prim_type} {prim_path}")
            except Exception as e:
                logger.error(f"Error removing attribute {attr_name}: {UnicodeHelper.safe_str(e)}")

    def clean_empty_custom_strings(self) -> Tuple[int, int]:
        """Main method to clean empty custom string attributes."""
        start_time = time.time()
        logger.info("=" * 50)
        logger.info("STARTING EMPTY CUSTOM STRING CLEANUP")
        logger.info("=" * 50)

        stage = USDOperations.get_stage()
        if not stage:
            logger.error("No USD stage found")
            return 0, 0

        # Reset counters
        self.found_count = 0
        self.removed_count = 0

        logger.info(f"USD Stage: {UnicodeHelper.safe_str(stage.GetRootLayer().identifier)}")

        # Get all meshes and xforms in the stage
        target_prims = USDOperations.get_target_prims(stage, ["Mesh", "Xform"])
        logger.info(f"Found {len(target_prims)} target prims to check")

        # Process each prim
        processed_count = 0
        for prim in target_prims:
            try:
                self.process_prim(prim)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing prim {UnicodeHelper.safe_str(prim.GetPath())}: {UnicodeHelper.safe_str(e)}")

        total_time = time.time() - start_time

        logger.info("=" * 50)
        logger.info("EMPTY CUSTOM STRING CLEANUP COMPLETED")
        logger.info("=" * 50)
        logger.info(f"Processed {processed_count} prims")
        logger.info(f"Found {self.found_count} empty custom strings")
        logger.info(f"Removed {self.removed_count} empty custom string properties")
        logger.info(f"Total time: {total_time:.3f}s")
        logger.info("=" * 50)

        return self.found_count, self.removed_count


class MaterialDeltaCleaner:
    """Handles removal of inactive material deltas from both USD stage and layers."""

    def __init__(self):
        self.found_count = 0
        self.deleted_count = 0
        self.specs_to_delete: Set[Tuple] = set()
        self.stage_materials_to_delete: List[Usd.Prim] = []
        self.debug_info = defaultdict(list)  # For detailed debugging
        self.execution_stats = {
            'stage_search_time': 0,
            'layer_search_time': 0,
            'stage_delete_time': 0,
            'layer_delete_time': 0,
            'total_prims_checked': 0,
            'total_specs_checked': 0
        }

    def _is_inactive_material_spec(self, spec) -> bool:
        """Check if a spec is an inactive material override."""
        try:
            spec_type = UnicodeHelper.safe_str(spec.typeName)
            spec_specifier = UnicodeHelper.safe_str(spec.specifier)

            is_material = spec_type == "Material"
            is_override = spec_specifier == UnicodeHelper.safe_str(Sdf.SpecifierOver)

            try:
                has_active_false = spec.HasInfo('active') and spec.GetInfo('active') == False
            except Exception:
                has_active_false = False

            return (is_material and is_override and has_active_false) or (is_override and has_active_false)
        except Exception:
            return False

    def _traverse_specs_recursive(self, spec, layer, layer_id: str = "", current_path: str = "") -> int:
        """Recursively traverse prim specs to find inactive materials."""
        if not spec:
            return 0

        specs_checked = 1  # Count this spec

        try:
            spec_name = UnicodeHelper.safe_str(spec.name)
            spec_type = UnicodeHelper.safe_str(spec.typeName)
            spec_specifier = UnicodeHelper.safe_str(spec.specifier)

            # Build the full path
            full_path = f"{current_path}/{spec_name}" if current_path else f"/{spec_name}"

            logger.debug(f"Checking spec: {full_path}, type: {spec_type}, specifier: {spec_specifier}")

            if self._is_inactive_material_spec(spec):
                self.specs_to_delete.add((layer, Sdf.Path(full_path)))
                logger.info(f"*** FOUND INACTIVE MATERIAL SPEC: {full_path} (type: {spec_type}) in layer: {layer_id}")

                # Store debug info
                self.debug_info['layer_inactive_materials'].append({
                    'path': full_path,
                    'type': spec_type,
                    'layer': layer_id,
                    'specifier': spec_specifier
                })

            # Recursively check children
            for child in spec.nameChildren:
                specs_checked += self._traverse_specs_recursive(child, layer, layer_id, full_path)

        except Exception as e:
            logger.error(f"Error processing spec: {UnicodeHelper.safe_str(e)}")

        return specs_checked

    def _find_specs_in_layers(self, stage: Usd.Stage) -> None:
        """Find inactive material specs in all layers."""
        start_time = time.time()
        logger.info("=== Starting layer search for inactive material specs ===")

        layers_to_check = USDOperations.get_layers_to_check(stage)
        total_specs_checked = 0
        layer_stats = {}

        for layer in layers_to_check:
            if not layer:
                continue

            try:
                layer_id = UnicodeHelper.safe_str(layer.identifier)
                logger.info(f"--- Checking layer: {layer_id} ---")
                layer_specs_checked = 0
                layer_inactive_found = 0

            except Exception:
                logger.info("--- Checking layer with encoding issues ---")
                layer_id = "unknown_layer"
                layer_specs_checked = 0
                layer_inactive_found = 0

            # Start from root prims
            for root_prim in layer.rootPrims:
                layer_specs_checked += self._traverse_specs_recursive(root_prim, layer, layer_id)
                layer_inactive_found = len([s for s in self.specs_to_delete if s[0] == layer])

            total_specs_checked += layer_specs_checked
            layer_stats[layer_id] = {
                'specs_checked': layer_specs_checked,
                'inactive_found': layer_inactive_found
            }

            logger.info(f"  - Layer {layer_id}: checked {layer_specs_checked} specs, found {layer_inactive_found} inactive")

        self.execution_stats['layer_search_time'] = time.time() - start_time
        self.execution_stats['total_specs_checked'] = total_specs_checked

        logger.info(f"=== Layer search completed ===")
        logger.info(f"  - Total layers checked: {len(layers_to_check)}")
        logger.info(f"  - Total specs checked: {total_specs_checked}")
        logger.info(f"  - Total inactive material specs found: {len(self.specs_to_delete)}")
        logger.info(f"  - Search time: {self.execution_stats['layer_search_time']:.3f}s")

        # Store detailed layer stats
        self.debug_info['layer_stats'] = layer_stats

    def _find_inactive_materials_in_stage(self, stage: Usd.Stage) -> None:
        """Find inactive materials in the stage."""
        start_time = time.time()
        logger.info("=== Starting stage search for inactive materials ===")

        try:
            prim_range = Usd.PrimRange.AllPrims(stage.GetPseudoRoot())
            inactive_count = 0
            material_count = 0

            for prim in prim_range:
                try:
                    self.execution_stats['total_prims_checked'] += 1

                    if not prim.IsActive():
                        inactive_count += 1
                        prim_path = UnicodeHelper.safe_str(prim.GetPath())
                        prim_type = UnicodeHelper.safe_str(prim.GetTypeName())

                        # Only process Material types
                        if prim_type == "Material":
                            material_count += 1
                            logger.info(f"*** FOUND INACTIVE MATERIAL IN STAGE: {prim_path} (type: {prim_type})")
                            self.stage_materials_to_delete.append(prim)

                            # Store debug info
                            self.debug_info['stage_inactive_materials'].append({
                                'path': prim_path,
                                'type': prim_type,
                                'layer': UnicodeHelper.safe_str(stage.GetEditTarget().GetLayer().identifier)
                            })

                except Exception as e:
                    logger.error(f"Error processing prim: {UnicodeHelper.safe_str(e)}")

        except Exception as e:
            logger.error(f"Error in stage traversal: {UnicodeHelper.safe_str(e)}")

        self.execution_stats['stage_search_time'] = time.time() - start_time
        logger.info(f"=== Stage search completed ===")
        logger.info(f"  - Total prims checked: {self.execution_stats['total_prims_checked']}")
        logger.info(f"  - Inactive prims found: {inactive_count}")
        logger.info(f"  - Inactive materials found: {material_count}")
        logger.info(f"  - Search time: {self.execution_stats['stage_search_time']:.3f}s")

    def _find_specs_via_stage_traversal(self, stage: Usd.Stage) -> None:
        """Double-check by traversing inactive prims in the stage."""
        logger.info("Double-checking with stage traversal...")
        layers_to_check = USDOperations.get_layers_to_check(stage)

        try:
            prim_range = Usd.PrimRange.AllPrims(stage.GetPseudoRoot())
            for prim in prim_range:
                try:
                    if not prim.IsActive():
                        prim_path = UnicodeHelper.safe_str(prim.GetPath())
                        prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                        logger.info(f"Found inactive prim: {prim_path}, type: {prim_type}")

                        # Check if this exists as an override spec in any layer
                        for layer in layers_to_check:
                            if not layer:
                                continue
                            try:
                                prim_spec = layer.GetPrimAtPath(prim.GetPath())
                                if (prim_spec and
                                    UnicodeHelper.safe_str(prim_spec.specifier) == UnicodeHelper.safe_str(Sdf.SpecifierOver)):
                                    # Add to deletion list if not already there
                                    spec_tuple = (layer, prim.GetPath())
                                    if spec_tuple not in self.specs_to_delete:
                                        self.specs_to_delete.add(spec_tuple)
                                        logger.info(f"*** ADDED FROM STAGE TRAVERSAL: {prim_path}")
                            except Exception as e:
                                logger.error(f"Error checking prim spec: {UnicodeHelper.safe_str(e)}")
                except Exception as e:
                    logger.error(f"Error processing prim: {UnicodeHelper.safe_str(e)}")
        except Exception as e:
            logger.error(f"Error in stage traversal: {UnicodeHelper.safe_str(e)}")

    def _delete_spec(self, stage: Usd.Stage, layer, prim_path) -> bool:
        """Delete a single prim spec."""
        try:
            prim_spec = layer.GetPrimAtPath(prim_path)
            if not prim_spec:
                return False

            safe_prim_path = UnicodeHelper.safe_str(prim_path)
            safe_layer_id = UnicodeHelper.safe_str(layer.identifier)
            logger.info(f"Attempting to delete: {safe_prim_path} from {safe_layer_id}")

            # Try different removal methods
            success = False

            # Method 1: Use stage operations for current edit layer
            try:
                edit_target = stage.GetEditTarget()
                if edit_target.GetLayer() == layer:
                    stage.RemovePrim(prim_path)
                    success = True
                    logger.info(f"Removed via stage.RemovePrim: {safe_prim_path}")
                else:
                    # For other layers, use layer-level operations
                    if hasattr(layer, 'RemovePrimSpec'):
                        layer.RemovePrimSpec(prim_path)
                        success = True
                        logger.info(f"Removed with RemovePrimSpec: {safe_prim_path}")
                    else:
                        # Alternative: Clear properties and remove if inert
                        prim_spec.specifier = Sdf.SpecifierOver
                        prim_spec.ClearInfo('active')
                        if not prim_spec.properties and not prim_spec.nameChildren:
                            parent_path = prim_path.GetParentPath()
                            parent_spec = layer.GetPrimAtPath(parent_path)
                            if parent_spec:
                                parent_spec.RemoveNameChild(prim_spec)
                        success = True
                        logger.info(f"Cleared and removed: {safe_prim_path}")
            except Exception as e:
                logger.error(f"Method 1 failed: {UnicodeHelper.safe_str(e)}")

            # Method 2: Alternative approach
            if not success:
                try:
                    parent_path = prim_path.GetParentPath()
                    if parent_path != Sdf.Path.absoluteRootPath:
                        parent_spec = layer.GetPrimAtPath(parent_path)
                        if parent_spec and prim_spec.name in [child.name for child in parent_spec.nameChildren]:
                            parent_spec.RemoveNameChild(prim_spec)
                            success = True
                            logger.info(f"Removed from parent: {safe_prim_path}")
                    else:
                        # It's a root prim
                        if prim_spec.name in [child.name for child in layer.rootPrims]:
                            layer.RemoveRootPrim(prim_spec)
                            success = True
                            logger.info(f"Removed root prim: {safe_prim_path}")
                except Exception as e:
                    logger.error(f"Method 2 failed: {UnicodeHelper.safe_str(e)}")

            return success

        except Exception as e:
            safe_prim_path = UnicodeHelper.safe_str(prim_path)
            logger.error(f"Error deleting {safe_prim_path}: {UnicodeHelper.safe_str(e)}")
            return False

    def _delete_stage_material(self, stage: Usd.Stage, material: Usd.Prim) -> bool:
        """Delete a single material from stage."""
        try:
            material_path = UnicodeHelper.safe_str(material.GetPath())
            material_type = UnicodeHelper.safe_str(material.GetTypeName())
            logger.info(f"Attempting to delete inactive material from stage: {material_path} (type: {material_type})")

            # Try to delete the material from stage
            success = False
            try:
                stage.RemovePrim(material.GetPath())
                success = True
                logger.info(f"Successfully deleted material from stage: {material_path}")

                # Store debug info
                self.debug_info['stage_deleted_materials'].append({
                    'path': material_path,
                    'type': material_type,
                    'success': True
                })
            except Exception as e:
                error_msg = UnicodeHelper.safe_str(e)
                logger.error(f"Failed to delete material from stage {material_path}: {error_msg}")

                # Store debug info
                self.debug_info['stage_deleted_materials'].append({
                    'path': material_path,
                    'type': material_type,
                    'success': False,
                    'error': error_msg
                })

            return success

        except Exception as e:
            logger.error(f"Error deleting stage material: {UnicodeHelper.safe_str(e)}")
            return False

    def clean_inactive_material_deltas(self) -> Tuple[int, int]:
        """Main method to clean inactive material deltas from both stage and layers."""
        total_start_time = time.time()
        logger.info("=" * 60)
        logger.info("STARTING INACTIVE MATERIAL DELTA CLEANUP OPERATION")
        logger.info("=" * 60)

        stage = USDOperations.get_stage()
        if not stage:
            logger.error("No USD stage found")
            return 0, 0

        # Reset counters and debug info
        self.found_count = 0
        self.deleted_count = 0
        self.specs_to_delete = set()
        self.stage_materials_to_delete = []
        self.debug_info.clear()
        self.execution_stats = {
            'stage_search_time': 0,
            'layer_search_time': 0,
            'stage_delete_time': 0,
            'layer_delete_time': 0,
            'total_prims_checked': 0,
            'total_specs_checked': 0
        }

        logger.info(f"USD Stage: {UnicodeHelper.safe_str(stage.GetRootLayer().identifier)}")

        # Phase 1: Find inactive materials in stage
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 1: SEARCHING STAGE FOR INACTIVE MATERIALS")
        logger.info("=" * 40)
        self._find_inactive_materials_in_stage(stage)

        # Phase 2: Find specs in layers
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 2: SEARCHING LAYERS FOR INACTIVE MATERIAL SPECS")
        logger.info("=" * 40)
        self._find_specs_in_layers(stage)

        # Update found count (stage materials + layer specs)
        stage_count = len(self.stage_materials_to_delete)
        layer_count = len(self.specs_to_delete)
        self.found_count = stage_count + layer_count

        logger.info(f"\nSUMMARY OF FINDINGS:")
        logger.info(f"  - Stage inactive materials: {stage_count}")
        logger.info(f"  - Layer inactive material specs: {layer_count}")
        logger.info(f"  - Total to delete: {self.found_count}")

        # Phase 3: Delete stage materials first
        stage_deleted = 0
        if self.stage_materials_to_delete:
            logger.info("\n" + "=" * 40)
            logger.info("PHASE 3: DELETING INACTIVE MATERIALS FROM STAGE")
            logger.info("=" * 40)

            delete_start_time = time.time()
            with Sdf.ChangeBlock():
                for i, material in enumerate(self.stage_materials_to_delete, 1):
                    logger.info(f"Deleting stage material {i}/{stage_count}: {UnicodeHelper.safe_str(material.GetPath())}")
                    if self._delete_stage_material(stage, material):
                        stage_deleted += 1
            self.execution_stats['stage_delete_time'] = time.time() - delete_start_time
            logger.info(f"Deleted {stage_deleted}/{stage_count} inactive materials from stage")

        # Phase 4: Delete layer specs
        layer_deleted = 0
        if self.specs_to_delete:
            logger.info("\n" + "=" * 40)
            logger.info("PHASE 4: DELETING INACTIVE MATERIAL SPECS FROM LAYERS")
            logger.info("=" * 40)

            delete_start_time = time.time()
            with Sdf.ChangeBlock():
                for i, (layer, prim_path) in enumerate(self.specs_to_delete, 1):
                    layer_id = UnicodeHelper.safe_str(layer.identifier)
                    logger.info(f"Deleting layer material spec {i}/{layer_count}: {UnicodeHelper.safe_str(prim_path)} from {layer_id}")
                    if self._delete_spec(stage, layer, prim_path):
                        layer_deleted += 1
            self.execution_stats['layer_delete_time'] = time.time() - delete_start_time
            logger.info(f"Deleted {layer_deleted}/{layer_count} inactive material specs from layers")

        self.deleted_count = stage_deleted + layer_deleted
        total_time = time.time() - total_start_time

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("MATERIAL DELTA CLEANUP OPERATION COMPLETED")
        logger.info("=" * 60)

        if self.found_count == 0:
            logger.info("No inactive material deltas found")
        else:
            logger.info(f"Found {self.found_count} inactive material deltas total")
            logger.info(f"Deleted {self.deleted_count} inactive material deltas")
            logger.info(f"  - Stage: {stage_deleted}/{stage_count}")
            logger.info(f"  - Layers: {layer_deleted}/{layer_count}")

        logger.info(f"\nPERFORMANCE STATISTICS:")
        logger.info(f"  - Total execution time: {total_time:.3f}s")
        logger.info(f"  - Stage search time: {self.execution_stats['stage_search_time']:.3f}s")
        logger.info(f"  - Layer search time: {self.execution_stats['layer_search_time']:.3f}s")
        logger.info(f"  - Stage delete time: {self.execution_stats['stage_delete_time']:.3f}s")
        logger.info(f"  - Layer delete time: {self.execution_stats['layer_delete_time']:.3f}s")
        logger.info(f"  - Total prims checked: {self.execution_stats['total_prims_checked']}")
        logger.info(f"  - Total specs checked: {self.execution_stats['total_specs_checked']}")

        # Debug info summary
        if self.debug_info:
            logger.info(f"\nDEBUG INFORMATION:")
            for key, value in self.debug_info.items():
                if isinstance(value, list):
                    logger.info(f"  - {key}: {len(value)} items")
                else:
                    logger.info(f"  - {key}: {value}")

        logger.info("=" * 60)
        return self.found_count, self.deleted_count

    def get_debug_report(self) -> str:
        """Generate a detailed debug report for analysis."""
        report = []
        report.append("=" * 80)
        report.append("MATERIAL DELTA CLEANER DEBUG REPORT")
        report.append("=" * 80)

        # Execution statistics
        report.append("\nEXECUTION STATISTICS:")
        for key, value in self.execution_stats.items():
            if isinstance(value, float):
                report.append(f"  {key}: {value:.3f}s")
            else:
                report.append(f"  {key}: {value}")

        # Stage materials found
        if self.debug_info.get('stage_inactive_materials'):
            report.append(f"\nSTAGE INACTIVE MATERIALS ({len(self.debug_info['stage_inactive_materials'])}):")
            for material_info in self.debug_info['stage_inactive_materials']:
                report.append(f"  - {material_info['path']} ({material_info['type']}) in {material_info['layer']}")

        # Layer material specs found
        if self.debug_info.get('layer_inactive_materials'):
            report.append(f"\nLAYER INACTIVE MATERIAL SPECS ({len(self.debug_info['layer_inactive_materials'])}):")
            for spec_info in self.debug_info['layer_inactive_materials']:
                report.append(f"  - {spec_info['path']} ({spec_info['type']}) in {spec_info['layer']}")

        # Deletion results
        if self.debug_info.get('stage_deleted_materials'):
            report.append(f"\nSTAGE DELETION RESULTS ({len(self.debug_info['stage_deleted_materials'])}):")
            for material_info in self.debug_info['stage_deleted_materials']:
                status = "SUCCESS" if material_info['success'] else "FAILED"
                report.append(f"  {status} {material_info['path']} ({material_info['type']})")
                if not material_info['success']:
                    report.append(f"    Error: {material_info.get('error', 'Unknown error')}")

        # Layer statistics
        if self.debug_info.get('layer_stats'):
            report.append(f"\nLAYER STATISTICS:")
            for layer_id, stats in self.debug_info['layer_stats'].items():
                report.append(f"  {layer_id}: {stats['specs_checked']} checked, {stats['inactive_found']} inactive")

        report.append("=" * 80)
        return "\n".join(report)


class InactivePrimCleaner:
    """Handles removal of inactive mesh and Xform prims from both USD stage and layers."""

    def __init__(self):
        self.found_count = 0
        self.deleted_count = 0
        self.specs_to_delete: Set[Tuple] = set()
        self.stage_prims_to_delete: List[Usd.Prim] = []
        self.debug_info = defaultdict(list)  # For detailed debugging
        self.execution_stats = {
            'stage_search_time': 0,
            'layer_search_time': 0,
            'stage_delete_time': 0,
            'layer_delete_time': 0,
            'total_prims_checked': 0,
            'total_specs_checked': 0
        }

    def _is_inactive_prim_spec(self, spec) -> bool:
        """Check if a spec is an inactive mesh or Xform override."""
        try:
            spec_type = UnicodeHelper.safe_str(spec.typeName)
            spec_specifier = UnicodeHelper.safe_str(spec.specifier)

            is_target_type = spec_type in ["Mesh", "Xform"]
            is_override = spec_specifier == UnicodeHelper.safe_str(Sdf.SpecifierOver)

            try:
                has_active_false = spec.HasInfo('active') and spec.GetInfo('active') == False
            except Exception:
                has_active_false = False

            return is_target_type and is_override and has_active_false
        except Exception:
            return False

    def _traverse_specs_recursive(self, spec, layer, layer_id: str = "", current_path: str = "") -> int:
        """Recursively traverse prim specs to find inactive mesh/Xform prims."""
        if not spec:
            return 0

        specs_checked = 1  # Count this spec

        try:
            spec_name = UnicodeHelper.safe_str(spec.name)
            spec_type = UnicodeHelper.safe_str(spec.typeName)
            spec_specifier = UnicodeHelper.safe_str(spec.specifier)

            # Build the full path
            full_path = f"{current_path}/{spec_name}" if current_path else f"/{spec_name}"

            logger.debug(f"Checking spec: {full_path}, type: {spec_type}, specifier: {spec_specifier}")

            if self._is_inactive_prim_spec(spec):
                self.specs_to_delete.add((layer, Sdf.Path(full_path)))
                logger.info(f"*** FOUND INACTIVE PRIM SPEC: {full_path} (type: {spec_type}) in layer: {layer_id}")

                # Store debug info
                self.debug_info['layer_inactive_specs'].append({
                    'path': full_path,
                    'type': spec_type,
                    'layer': layer_id,
                    'specifier': spec_specifier
                })

            # Recursively check children
            for child in spec.nameChildren:
                specs_checked += self._traverse_specs_recursive(child, layer, layer_id, full_path)

        except Exception as e:
            logger.error(f"Error processing spec: {UnicodeHelper.safe_str(e)}")

        return specs_checked

    def _find_specs_in_layers(self, stage: Usd.Stage) -> None:
        """Find inactive mesh/Xform specs in all layers."""
        start_time = time.time()
        logger.info("=== Starting layer search for inactive prim specs ===")

        layers_to_check = USDOperations.get_layers_to_check(stage)
        total_specs_checked = 0
        layer_stats = {}

        for layer in layers_to_check:
            if not layer:
                continue

            try:
                layer_id = UnicodeHelper.safe_str(layer.identifier)
                logger.info(f"--- Checking layer: {layer_id} ---")
                layer_specs_checked = 0
                layer_inactive_found = 0

            except Exception:
                logger.info("--- Checking layer with encoding issues ---")
                layer_id = "unknown_layer"
                layer_specs_checked = 0
                layer_inactive_found = 0

            # Start from root prims
            for root_prim in layer.rootPrims:
                layer_specs_checked += self._traverse_specs_recursive(root_prim, layer, layer_id)
                layer_inactive_found = len([s for s in self.specs_to_delete if s[0] == layer])

            total_specs_checked += layer_specs_checked
            layer_stats[layer_id] = {
                'specs_checked': layer_specs_checked,
                'inactive_found': layer_inactive_found
            }

            logger.info(f"  - Layer {layer_id}: checked {layer_specs_checked} specs, found {layer_inactive_found} inactive")

        self.execution_stats['layer_search_time'] = time.time() - start_time
        self.execution_stats['total_specs_checked'] = total_specs_checked

        logger.info(f"=== Layer search completed ===")
        logger.info(f"  - Total layers checked: {len(layers_to_check)}")
        logger.info(f"  - Total specs checked: {total_specs_checked}")
        logger.info(f"  - Total inactive specs found: {len(self.specs_to_delete)}")
        logger.info(f"  - Search time: {self.execution_stats['layer_search_time']:.3f}s")

        # Store detailed layer stats
        self.debug_info['layer_stats'] = layer_stats

    def _find_inactive_prims_in_stage(self, stage: Usd.Stage) -> None:
        """Find inactive mesh/Xform prims in the stage."""
        start_time = time.time()
        logger.info("=== Starting stage search for inactive prims ===")

        try:
            prim_range = Usd.PrimRange.AllPrims(stage.GetPseudoRoot())
            inactive_count = 0
            target_type_count = 0

            for prim in prim_range:
                try:
                    self.execution_stats['total_prims_checked'] += 1

                    if not prim.IsActive():
                        inactive_count += 1
                        prim_path = UnicodeHelper.safe_str(prim.GetPath())
                        prim_type = UnicodeHelper.safe_str(prim.GetTypeName())

                        # Only process Mesh and Xform types
                        if prim_type in ["Mesh", "Xform"]:
                            target_type_count += 1
                            logger.info(f"*** FOUND INACTIVE PRIM IN STAGE: {prim_path} (type: {prim_type})")
                            self.stage_prims_to_delete.append(prim)

                            # Store debug info
                            self.debug_info['stage_inactive_prims'].append({
                                'path': prim_path,
                                'type': prim_type,
                                'layer': UnicodeHelper.safe_str(stage.GetEditTarget().GetLayer().identifier)
                            })

                except Exception as e:
                    logger.error(f"Error processing prim: {UnicodeHelper.safe_str(e)}")

        except Exception as e:
            logger.error(f"Error in stage traversal: {UnicodeHelper.safe_str(e)}")

        self.execution_stats['stage_search_time'] = time.time() - start_time
        logger.info(f"=== Stage search completed ===")
        logger.info(f"  - Total prims checked: {self.execution_stats['total_prims_checked']}")
        logger.info(f"  - Inactive prims found: {inactive_count}")
        logger.info(f"  - Target type (Mesh/Xform) inactive: {target_type_count}")
        logger.info(f"  - Search time: {self.execution_stats['stage_search_time']:.3f}s")

    def _delete_spec(self, stage: Usd.Stage, layer, prim_path) -> bool:
        """Delete a single prim spec from layer."""
        try:
            prim_spec = layer.GetPrimAtPath(prim_path)
            if not prim_spec:
                return False

            safe_prim_path = UnicodeHelper.safe_str(prim_path)
            safe_layer_id = UnicodeHelper.safe_str(layer.identifier)
            logger.info(f"Attempting to delete inactive prim spec: {safe_prim_path} from {safe_layer_id}")

            # Try different removal methods
            success = False

            # Method 1: Use stage operations for current edit layer
            try:
                edit_target = stage.GetEditTarget()
                if edit_target.GetLayer() == layer:
                    stage.RemovePrim(prim_path)
                    success = True
                    logger.info(f"Removed spec via stage.RemovePrim: {safe_prim_path}")
                else:
                    # For other layers, use layer-level operations
                    if hasattr(layer, 'RemovePrimSpec'):
                        layer.RemovePrimSpec(prim_path)
                        success = True
                        logger.info(f"Removed spec with RemovePrimSpec: {safe_prim_path}")
                    else:
                        # Alternative: Clear properties and remove if inert
                        prim_spec.specifier = Sdf.SpecifierOver
                        prim_spec.ClearInfo('active')
                        if not prim_spec.properties and not prim_spec.nameChildren:
                            parent_path = prim_path.GetParentPath()
                            parent_spec = layer.GetPrimAtPath(parent_path)
                            if parent_spec:
                                parent_spec.RemoveNameChild(prim_spec)
                        success = True
                        logger.info(f"Cleared and removed spec: {safe_prim_path}")
            except Exception as e:
                logger.error(f"Method 1 failed: {UnicodeHelper.safe_str(e)}")

            # Method 2: Alternative approach
            if not success:
                try:
                    parent_path = prim_path.GetParentPath()
                    if parent_path != Sdf.Path.absoluteRootPath:
                        parent_spec = layer.GetPrimAtPath(parent_path)
                        if parent_spec and prim_spec.name in [child.name for child in parent_spec.nameChildren]:
                            parent_spec.RemoveNameChild(prim_spec)
                            success = True
                            logger.info(f"Removed spec from parent: {safe_prim_path}")
                    else:
                        # It's a root prim
                        if prim_spec.name in [child.name for child in layer.rootPrims]:
                            layer.RemoveRootPrim(prim_spec)
                            success = True
                            logger.info(f"Removed root prim spec: {safe_prim_path}")
                except Exception as e:
                    logger.error(f"Method 2 failed: {UnicodeHelper.safe_str(e)}")

            return success

        except Exception as e:
            safe_prim_path = UnicodeHelper.safe_str(prim_path)
            logger.error(f"Error deleting spec {safe_prim_path}: {UnicodeHelper.safe_str(e)}")
            return False

    def _delete_stage_prim(self, stage: Usd.Stage, prim: Usd.Prim) -> bool:
        """Delete a single prim from stage."""
        try:
            prim_path = UnicodeHelper.safe_str(prim.GetPath())
            prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
            logger.info(f"Attempting to delete inactive prim from stage: {prim_path} (type: {prim_type})")

            # Try to delete the prim from stage
            success = False
            try:
                stage.RemovePrim(prim.GetPath())
                success = True
                logger.info(f"Successfully deleted prim from stage: {prim_path}")

                # Store debug info
                self.debug_info['stage_deleted_prims'].append({
                    'path': prim_path,
                    'type': prim_type,
                    'success': True
                })
            except Exception as e:
                error_msg = UnicodeHelper.safe_str(e)
                logger.error(f"Failed to delete prim from stage {prim_path}: {error_msg}")

                # Store debug info
                self.debug_info['stage_deleted_prims'].append({
                    'path': prim_path,
                    'type': prim_type,
                    'success': False,
                    'error': error_msg
                })

            return success

        except Exception as e:
            logger.error(f"Error deleting stage prim: {UnicodeHelper.safe_str(e)}")
            return False

    def clean_inactive_prims(self) -> Tuple[int, int]:
        """Main method to clean inactive mesh and Xform prims from both stage and layers."""
        total_start_time = time.time()
        logger.info("=" * 60)
        logger.info("STARTING INACTIVE PRIM CLEANUP OPERATION")
        logger.info("=" * 60)

        stage = USDOperations.get_stage()
        if not stage:
            logger.error("No USD stage found")
            return 0, 0

        # Reset counters and debug info
        self.found_count = 0
        self.deleted_count = 0
        self.specs_to_delete = set()
        self.stage_prims_to_delete = []
        self.debug_info.clear()
        self.execution_stats = {
            'stage_search_time': 0,
            'layer_search_time': 0,
            'stage_delete_time': 0,
            'layer_delete_time': 0,
            'total_prims_checked': 0,
            'total_specs_checked': 0
        }

        logger.info(f"USD Stage: {UnicodeHelper.safe_str(stage.GetRootLayer().identifier)}")

        # Phase 1: Find inactive prims in stage
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 1: SEARCHING STAGE FOR INACTIVE PRIMS")
        logger.info("=" * 40)
        self._find_inactive_prims_in_stage(stage)

        # Phase 2: Find specs in layers
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 2: SEARCHING LAYERS FOR INACTIVE SPECS")
        logger.info("=" * 40)
        self._find_specs_in_layers(stage)

        # Update found count (stage prims + layer specs)
        stage_count = len(self.stage_prims_to_delete)
        layer_count = len(self.specs_to_delete)
        self.found_count = stage_count + layer_count

        logger.info(f"\nSUMMARY OF FINDINGS:")
        logger.info(f"  - Stage inactive prims: {stage_count}")
        logger.info(f"  - Layer inactive specs: {layer_count}")
        logger.info(f"  - Total to delete: {self.found_count}")

        # Phase 3: Delete stage prims first
        stage_deleted = 0
        if self.stage_prims_to_delete:
            logger.info("\n" + "=" * 40)
            logger.info("PHASE 3: DELETING INACTIVE PRIMS FROM STAGE")
            logger.info("=" * 40)

            delete_start_time = time.time()
            with Sdf.ChangeBlock():
                for i, prim in enumerate(self.stage_prims_to_delete, 1):
                    logger.info(f"Deleting stage prim {i}/{stage_count}: {UnicodeHelper.safe_str(prim.GetPath())}")
                    if self._delete_stage_prim(stage, prim):
                        stage_deleted += 1
            self.execution_stats['stage_delete_time'] = time.time() - delete_start_time
            logger.info(f"Deleted {stage_deleted}/{stage_count} inactive prims from stage")

        # Phase 4: Delete layer specs
        layer_deleted = 0
        if self.specs_to_delete:
            logger.info("\n" + "=" * 40)
            logger.info("PHASE 4: DELETING INACTIVE SPECS FROM LAYERS")
            logger.info("=" * 40)

            delete_start_time = time.time()
            with Sdf.ChangeBlock():
                for i, (layer, prim_path) in enumerate(self.specs_to_delete, 1):
                    layer_id = UnicodeHelper.safe_str(layer.identifier)
                    logger.info(f"Deleting layer spec {i}/{layer_count}: {UnicodeHelper.safe_str(prim_path)} from {layer_id}")
                    if self._delete_spec(stage, layer, prim_path):
                        layer_deleted += 1
            self.execution_stats['layer_delete_time'] = time.time() - delete_start_time
            logger.info(f"Deleted {layer_deleted}/{layer_count} inactive specs from layers")

        self.deleted_count = stage_deleted + layer_deleted
        total_time = time.time() - total_start_time

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP OPERATION COMPLETED")
        logger.info("=" * 60)

        if self.found_count == 0:
            logger.info("No inactive mesh or Xform prims found")
        else:
            logger.info(f"Found {self.found_count} inactive prims total")
            logger.info(f"Deleted {self.deleted_count} inactive prims")
            logger.info(f"  - Stage: {stage_deleted}/{stage_count}")
            logger.info(f"  - Layers: {layer_deleted}/{layer_count}")

        logger.info(f"\nPERFORMANCE STATISTICS:")
        logger.info(f"  - Total execution time: {total_time:.3f}s")
        logger.info(f"  - Stage search time: {self.execution_stats['stage_search_time']:.3f}s")
        logger.info(f"  - Layer search time: {self.execution_stats['layer_search_time']:.3f}s")
        logger.info(f"  - Stage delete time: {self.execution_stats['stage_delete_time']:.3f}s")
        logger.info(f"  - Layer delete time: {self.execution_stats['layer_delete_time']:.3f}s")
        logger.info(f"  - Total prims checked: {self.execution_stats['total_prims_checked']}")
        logger.info(f"  - Total specs checked: {self.execution_stats['total_specs_checked']}")

        # Debug info summary
        if self.debug_info:
            logger.info(f"\nDEBUG INFORMATION:")
            for key, value in self.debug_info.items():
                if isinstance(value, list):
                    logger.info(f"  - {key}: {len(value)} items")
                else:
                    logger.info(f"  - {key}: {value}")

        logger.info("=" * 60)
        return self.found_count, self.deleted_count

    def get_debug_report(self) -> str:
        """Generate a detailed debug report for analysis."""
        report = []
        report.append("=" * 80)
        report.append("INACTIVE PRIM CLEANER DEBUG REPORT")
        report.append("=" * 80)

        # Execution statistics
        report.append("\nEXECUTION STATISTICS:")
        for key, value in self.execution_stats.items():
            if isinstance(value, float):
                report.append(f"  {key}: {value:.3f}s")
            else:
                report.append(f"  {key}: {value}")

        # Stage prims found
        if self.debug_info.get('stage_inactive_prims'):
            report.append(f"\nSTAGE INACTIVE PRIMS ({len(self.debug_info['stage_inactive_prims'])}):")
            for prim_info in self.debug_info['stage_inactive_prims']:
                report.append(f"  - {prim_info['path']} ({prim_info['type']}) in {prim_info['layer']}")

        # Layer specs found
        if self.debug_info.get('layer_inactive_specs'):
            report.append(f"\nLAYER INACTIVE SPECS ({len(self.debug_info['layer_inactive_specs'])}):")
            for spec_info in self.debug_info['layer_inactive_specs']:
                report.append(f"  - {spec_info['path']} ({spec_info['type']}) in {spec_info['layer']}")

        # Deletion results
        if self.debug_info.get('stage_deleted_prims'):
            report.append(f"\nSTAGE DELETION RESULTS ({len(self.debug_info['stage_deleted_prims'])}):")
            for prim_info in self.debug_info['stage_deleted_prims']:
                status = "SUCCESS" if prim_info['success'] else "FAILED"
                report.append(f"  {status} {prim_info['path']} ({prim_info['type']})")
                if not prim_info['success']:
                    report.append(f"    Error: {prim_info.get('error', 'Unknown error')}")

        # Layer statistics
        if self.debug_info.get('layer_stats'):
            report.append(f"\nLAYER STATISTICS:")
            for layer_id, stats in self.debug_info['layer_stats'].items():
                report.append(f"  {layer_id}: {stats['specs_checked']} checked, {stats['inactive_found']} inactive")

        report.append("=" * 80)
        return "\n".join(report)


# Functions available to other extensions
def some_public_function(x: int) -> int:
    """This is a public function that can be called from other extensions."""
    logger.info(f"some_public_function was called with {x}")
    return x ** x


def test_extension_functionality() -> bool:
    """Test function to verify extension functionality."""
    try:
        # Test UnicodeHelper
        test_str = UnicodeHelper.safe_str("test")
        assert test_str == "test"

        # Test USDOperations
        stage = USDOperations.get_stage()
        # Note: stage might be None if no USD stage is open, which is normal

        logger.info("Extension functionality test passed")
        return True
    except Exception as e:
        logger.error(f"Extension functionality test failed: {e}")
        return False


class MyExtension(omni.ext.IExt):
    """Main extension class for deleting custom string properties and material deltas."""

    def __init__(self):
        super().__init__()
        self._window: Optional[ui.Window] = None
        self._custom_string_cleaner = CustomStringCleaner()
        self._material_delta_cleaner = MaterialDeltaCleaner()
        self._inactive_prim_cleaner = InactivePrimCleaner()

    def on_startup(self, ext_id: str) -> None:
        """Called when the extension is activated."""
        logger.info("=" * 50)
        logger.info("USD CLEANER EXTENSION STARTUP")
        logger.info("=" * 50)

        # Test extension functionality
        if test_extension_functionality():
            logger.info("Extension functionality verified")
        else:
            logger.warning("Extension functionality test failed")

        # Create UI
        self._create_ui()
        logger.info("UI created successfully")
        logger.info("=" * 50)

    def _create_ui(self) -> None:
        """Create the extension UI."""
        self._window = ui.Window("USD Cleaner", width=280, height=480)

        with self._window.frame:
            with ui.VStack(spacing=3):
                # Header
                ui.Label("USD Scene Cleaner",
                        style={"font_size": 16, "color": 0xFFCCCCCC, "font_style": "bold"})

                ui.Spacer(height=3)

                # Status label
                self._status_label = ui.Label("Ready",
                                            style={"font_size": 14, "color": 0xFF88FF88})

                ui.Spacer(height=8)

                # === CUSTOM STRING MANAGEMENT SECTION ===
                ui.Label("Custom String Management",
                        style={"font_size": 14, "color": 0xFFCCCCCC, "font_style": "bold"})

                # Search custom string section (most commonly used)
                with ui.VStack(spacing=2):
                    # Search custom string input
                    with ui.HStack(spacing=3):
                        ui.Label("Search:", width=40, style={"font_size": 13})
                        self._search_custom_string_name = ui.StringField(height=20, style={"font_size": 13})
                        self._search_custom_string_name.model.set_value("")

                    # Search custom string button
                    ui.Button("Search Custom String",
                            clicked_fn=self._on_search_custom_string,
                            height=28,
                            style={"font_size": 14})

                ui.Spacer(height=5)

                # Add custom string section
                with ui.VStack(spacing=2):
                    # Name input
                    with ui.HStack(spacing=3):
                        ui.Label("Name:", width=40, style={"font_size": 13})
                        self._custom_string_name = ui.StringField(height=20, style={"font_size": 13})
                        self._custom_string_name.model.set_value("customString")

                    # Value input
                    with ui.HStack(spacing=3):
                        ui.Label("Value:", width=40, style={"font_size": 13})
                        self._custom_string_value = ui.StringField(height=20, style={"font_size": 13})
                        self._custom_string_value.model.set_value("")

                    # Add custom string button
                    ui.Button("Add Custom String to Selected",
                            clicked_fn=self._on_add_custom_string,
                            height=28,
                            style={"font_size": 14})

                ui.Spacer(height=8)

                # === CLEANUP TOOLS SECTION ===
                ui.Label("Cleanup Tools",
                        style={"font_size": 14, "color": 0xFFCCCCCC, "font_style": "bold"})

                # Cleanup buttons in logical order
                with ui.HStack(spacing=3):
                    # Search empty custom strings button (find issues first)
                    ui.Button("Search Empty Custom Strings",
                            clicked_fn=self._on_search_empty_custom_strings,
                            height=28,
                            style={"font_size": 14})

                    # Delete inactive prims button (most common cleanup)
                    ui.Button("Delete Inactive Prims",
                            clicked_fn=self._on_delete_inactive_prims,
                            height=28,
                            style={"font_size": 14})

                    # Delete material deltas button (specialized cleanup)
                    ui.Button("Delete Material Deltas",
                            clicked_fn=self._on_delete_material_delta,
                            height=28,
                            style={"font_size": 14})

                ui.Spacer(height=8)

                # === MESH OPTIMIZATION SECTION ===
                ui.Label("Mesh Optimization",
                        style={"font_size": 14, "color": 0xFFCCCCCC, "font_style": "bold"})

                # Make selected meshes single-sided button
                ui.Button("Make Selected Single-Sided",
                        clicked_fn=self._on_make_selected_single_sided,
                        height=28,
                        style={"font_size": 14})

                ui.Spacer(height=8)

                # === UTILITIES SECTION ===
                ui.Label("Utilities",
                        style={"font_size": 14, "color": 0xFFCCCCCC, "font_style": "bold"})

                # Debug report button
                ui.Button("Debug Report",
                        clicked_fn=self._on_debug_report,
                        height=24,
                        style={"font_size": 13})

    def _on_search_empty_custom_strings(self) -> None:
        """Handle search empty custom strings button click."""
        logger.info("Search Empty Custom Strings button clicked")
        try:
            found_count, removed_count = self._custom_string_cleaner.clean_empty_custom_strings()
            self._status_label.text = (f"Empty Custom Strings: {found_count} found, {removed_count} removed")
        except Exception as e:
            error_msg = f"Error in Search Empty Custom Strings: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def _on_delete_material_delta(self) -> None:
        """Handle delete material delta button click."""
        logger.info("DeleteMaterialDelta button clicked")
        try:
            found_count, deleted_count = self._material_delta_cleaner.clean_inactive_material_deltas()

            # Get detailed stats for UI display
            stats = self._material_delta_cleaner.execution_stats
            total_time = (stats['stage_search_time'] + stats['layer_search_time'] +
                         stats['stage_delete_time'] + stats['layer_delete_time'])

            self._status_label.text = (f"Material Deltas: {found_count} found, {deleted_count} deleted ({total_time:.1f}s)")
        except Exception as e:
            error_msg = f"Error in DeleteMaterialDelta: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def _on_delete_inactive_prims(self) -> None:
        """Handle delete inactive prims button click."""
        logger.info("DeleteInactivePrims button clicked")
        try:
            found_count, deleted_count = self._inactive_prim_cleaner.clean_inactive_prims()

            # Get detailed stats for UI display
            stats = self._inactive_prim_cleaner.execution_stats
            total_time = (stats['stage_search_time'] + stats['layer_search_time'] +
                         stats['stage_delete_time'] + stats['layer_delete_time'])

            self._status_label.text = (f"Inactive Prims: {found_count} found, {deleted_count} deleted ({total_time:.1f}s)")
        except Exception as e:
            error_msg = f"Error in DeleteInactivePrims: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def _on_add_custom_string(self) -> None:
        """Handle add custom string button click."""
        logger.info("Add Custom String to Selected button clicked")
        try:
            name = UnicodeHelper.safe_str(self._custom_string_name.model.get_value_as_string())
            value = UnicodeHelper.safe_str(self._custom_string_value.model.get_value_as_string())

            if not name:
                self._status_label.text = "Custom string name cannot be empty"
                logger.warning("Custom string name cannot be empty")
                return

            # Get the USD context and selection
            usd_context = omni.usd.get_context()
            selection = usd_context.get_selection().get_selected_prim_paths()

            if not selection:
                self._status_label.text = "No prims selected"
                logger.warning("No prims selected")
                return

            stage = USDOperations.get_stage()
            if not stage:
                self._status_label.text = "No USD stage found"
                logger.error("No USD stage found")
                return

            processed_count = 0
            added_count = 0

            def process_prim_recursively(prim: Usd.Prim) -> Tuple[int, int]:
                 """Recursively process a prim and its children for adding custom string."""
                 local_processed = 0
                 local_added = 0

                 try:
                     prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                     prim_path_str = UnicodeHelper.safe_str(prim.GetPath())

                     # Add custom string to all object types (Mesh, Xform, etc.)
                     # Check if the custom string already exists
                     if prim.HasAttribute(name):
                         logger.info(f"Custom string '{name}' already exists on {prim_path_str} ({prim_type})")
                         local_processed += 1
                     else:
                         # Create the attribute if it doesn't exist
                         attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.String)
                         attr.Set(value)
                         logger.info(f"Added custom string '{name}' with value '{value}' to {prim_path_str} ({prim_type})")
                         local_processed += 1
                         local_added += 1

                     # Recursively process children for all types
                     for child in prim.GetChildren():
                         child_processed, child_added = process_prim_recursively(child)
                         local_processed += child_processed
                         local_added += child_added

                 except Exception as e:
                     prim_path_str = UnicodeHelper.safe_str(prim.GetPath())
                     logger.error(f"Error processing prim {prim_path_str}: {UnicodeHelper.safe_str(e)}")

                 return local_processed, local_added

            # Process each selected prim
            for prim_path in selection:
                try:
                    prim = stage.GetPrimAtPath(prim_path)
                    if not prim:
                        continue

                    prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                    prim_path_str = UnicodeHelper.safe_str(prim_path)

                    logger.info(f"Processing selected prim: {prim_path_str} (type: {prim_type})")

                    # Process the prim and all its descendants
                    prim_processed, prim_added = process_prim_recursively(prim)
                    processed_count += prim_processed
                    added_count += prim_added

                except Exception as e:
                    prim_path_str = UnicodeHelper.safe_str(prim_path)
                    logger.error(f"Error processing selected prim {prim_path_str}: {UnicodeHelper.safe_str(e)}")

            # Update status based on results
            if added_count == 0:
                self._status_label.text = "No custom strings added to selection"
                logger.warning("No custom strings added to selection")
            else:
                self._status_label.text = f"Added {added_count} custom strings to {processed_count} selected prims"
                logger.info(f"Successfully added {added_count} custom strings to {processed_count} selected prims")

        except Exception as e:
            error_msg = f"Error adding custom string: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def _on_search_custom_string(self) -> None:
        """Handle search custom string button click."""
        logger.info("Search Custom String button clicked")
        try:
            search_name = UnicodeHelper.safe_str(self._search_custom_string_name.model.get_value_as_string())

            if not search_name:
                self._status_label.text = "Search name cannot be empty"
                logger.warning("Search name cannot be empty")
                return

            # Get the USD context and selection
            usd_context = omni.usd.get_context()
            selection = usd_context.get_selection().get_selected_prim_paths()

            stage = USDOperations.get_stage()
            if not stage:
                self._status_label.text = "No USD stage found"
                logger.error("No USD stage found")
                return

            found_count = 0
            search_results = []

            def search_prim_recursively(prim: Usd.Prim) -> int:
                """Recursively search a prim and its children for custom string."""
                local_found = 0

                try:
                    prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                    prim_path_str = UnicodeHelper.safe_str(prim.GetPath())

                    # Check if the prim has the custom string attribute
                    if prim.HasAttribute(search_name):
                        attr = prim.GetAttribute(search_name)
                        if attr:
                            try:
                                value = UnicodeHelper.safe_get_attr_value(attr)
                                if value is not None:
                                    search_results.append({
                                        'path': prim_path_str,
                                        'type': prim_type,
                                        'value': value
                                    })
                                    logger.info(f"Found custom string '{search_name}' = '{value}' on {prim_path_str} ({prim_type})")
                                    local_found += 1
                            except Exception as e:
                                logger.error(f"Error reading attribute value: {UnicodeHelper.safe_str(e)}")

                    # Recursively search children for all types
                    for child in prim.GetChildren():
                        local_found += search_prim_recursively(child)

                except Exception as e:
                    prim_path_str = UnicodeHelper.safe_str(prim.GetPath())
                    logger.error(f"Error searching prim {prim_path_str}: {UnicodeHelper.safe_str(e)}")

                return local_found

            # Determine search scope
            if selection:
                # Search only selected prims and their descendants
                logger.info(f"Searching custom string '{search_name}' in {len(selection)} selected prims")
                for prim_path in selection:
                    try:
                        prim = stage.GetPrimAtPath(prim_path)
                        if not prim:
                            continue

                        prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                        prim_path_str = UnicodeHelper.safe_str(prim_path)
                        logger.info(f"Searching selected prim: {prim_path_str} (type: {prim_type})")

                        # Search the prim and all its descendants
                        found_count += search_prim_recursively(prim)

                    except Exception as e:
                        prim_path_str = UnicodeHelper.safe_str(prim_path)
                        logger.error(f"Error processing selected prim {prim_path_str}: {UnicodeHelper.safe_str(e)}")
            else:
                # Search entire USD scene
                logger.info(f"Searching custom string '{search_name}' in entire USD scene")
                try:
                    # Start from root prims
                    for root_prim in stage.GetPseudoRoot().GetChildren():
                        found_count += search_prim_recursively(root_prim)
                except Exception as e:
                    logger.error(f"Error searching entire scene: {UnicodeHelper.safe_str(e)}")

            # Update status based on results
            if found_count == 0:
                scope_info = "selected items" if selection else "entire scene"
                self._status_label.text = f"No custom string '{search_name}' found in {scope_info}"
                logger.warning(f"No custom string '{search_name}' found in {scope_info}")
            else:
                scope_info = f"{len(selection)} selected items" if selection else "entire scene"
                self._status_label.text = f"Found {found_count} instances of '{search_name}' in {scope_info}"
                logger.info(f"Found {found_count} instances of custom string '{search_name}' in {scope_info}")

                # Log detailed results
                logger.info("=== SEARCH RESULTS ===")
                for result in search_results:
                    logger.info(f"  {result['path']} ({result['type']}): '{result['value']}'")
                logger.info("=====================")

                # Auto-select found items
                try:
                    # Get the selection interface
                    selection_interface = usd_context.get_selection()

                    # Create list of path strings to select (not Sdf.Path objects)
                    paths_to_select = [result['path'] for result in search_results]

                    # Clear current selection and select found items
                    selection_interface.clear_selected_prim_paths()
                    selection_interface.set_selected_prim_paths(paths_to_select, False)

                    logger.info(f"Auto-selected {len(paths_to_select)} found items")
                    self._status_label.text = f"Found and selected {found_count} instances of '{search_name}' in {scope_info}"

                except Exception as e:
                    error_msg = f"Error auto-selecting found items: {UnicodeHelper.safe_str(e)}"
                    logger.error(error_msg)
                    # Don't change the status label here, keep the search results

        except Exception as e:
            error_msg = f"Error searching custom string: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def _on_debug_report(self) -> None:
        """Handle debug report button click."""
        logger.info("Debug Report button clicked")
        try:
            # Generate reports for both cleaners
            prim_debug_report = self._inactive_prim_cleaner.get_debug_report()
            material_debug_report = self._material_delta_cleaner.get_debug_report()

            logger.info("=== INACTIVE PRIM CLEANER DEBUG REPORT ===")
            logger.info(prim_debug_report)
            logger.info("\n=== MATERIAL DELTA CLEANER DEBUG REPORT ===")
            logger.info(material_debug_report)

            self._status_label.text = (f"Debug reports generated - check console")
        except Exception as e:
            error_msg = f"Error generating debug report: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def _on_make_selected_single_sided(self) -> None:
        """Handle make selected meshes single-sided button click."""
        logger.info("Make Selected Single-Sided button clicked")
        try:
            # Get the USD context and selection
            usd_context = omni.usd.get_context()
            selection = usd_context.get_selection().get_selected_prim_paths()

            if not selection:
                self._status_label.text = "No prims selected"
                logger.warning("No prims selected")
                return

            stage = USDOperations.get_stage()
            if not stage:
                self._status_label.text = "No USD stage found"
                logger.error("No USD stage found")
                return

            processed_count = 0
            mesh_count = 0
            container_count = 0

            def process_prim_recursively(prim: Usd.Prim) -> Tuple[int, int]:
                """Recursively process a prim and its children for single-sided meshes."""
                local_processed = 0
                local_mesh_count = 0

                try:
                    prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                    prim_path_str = UnicodeHelper.safe_str(prim.GetPath())

                    # If it's a mesh, make it single-sided
                    if prim_type == "Mesh":
                        local_mesh_count += 1

                        # Get or create the singleSided attribute
                        single_sided_attr = prim.GetAttribute("singleSided")
                        if not single_sided_attr:
                            # Create the attribute if it doesn't exist
                            single_sided_attr = prim.CreateAttribute("singleSided", Sdf.ValueTypeNames.Bool)

                        # Set the value to True (1)
                        single_sided_attr.Set(True)
                        local_processed += 1

                        logger.info(f"Set singleSided=True for mesh: {prim_path_str}")

                    # If it's a container type (Xform, Scope), recursively process children
                    elif prim_type in ["Xform", "Scope"]:
                        logger.debug(f"Processing container {prim_type}: {prim_path_str}")

                        # Get all children and process them recursively
                        for child in prim.GetChildren():
                            child_processed, child_mesh_count = process_prim_recursively(child)
                            local_processed += child_processed
                            local_mesh_count += child_mesh_count

                    # For other types, just process children without special handling
                    else:
                        logger.debug(f"Processing other type {prim_type}: {prim_path_str}")

                        # Still process children for other types
                        for child in prim.GetChildren():
                            child_processed, child_mesh_count = process_prim_recursively(child)
                            local_processed += child_processed
                            local_mesh_count += child_mesh_count

                except Exception as e:
                    prim_path_str = UnicodeHelper.safe_str(prim.GetPath())
                    logger.error(f"Error processing prim {prim_path_str}: {UnicodeHelper.safe_str(e)}")

                return local_processed, local_mesh_count

            # Process each selected prim
            for prim_path in selection:
                try:
                    prim = stage.GetPrimAtPath(prim_path)
                    if not prim:
                        continue

                    prim_type = UnicodeHelper.safe_str(prim.GetTypeName())
                    prim_path_str = UnicodeHelper.safe_str(prim_path)

                    logger.info(f"Processing selected prim: {prim_path_str} (type: {prim_type})")

                    # Process the prim and all its descendants
                    prim_processed, prim_mesh_count = process_prim_recursively(prim)
                    processed_count += prim_processed
                    mesh_count += prim_mesh_count

                    # Count containers for logging
                    if prim_type in ["Xform", "Scope"]:
                        container_count += 1

                except Exception as e:
                    prim_path_str = UnicodeHelper.safe_str(prim_path)
                    logger.error(f"Error processing selected prim {prim_path_str}: {UnicodeHelper.safe_str(e)}")

            # Update status based on results
            if mesh_count == 0:
                self._status_label.text = "No meshes found in selection"
                logger.warning("No meshes found in selection")
            else:
                container_info = f" ({container_count} containers)" if container_count > 0 else ""
                self._status_label.text = f"Made {processed_count}/{mesh_count} meshes single-sided{container_info}"
                logger.info(f"Successfully made {processed_count}/{mesh_count} meshes single-sided{container_info}")

        except Exception as e:
            error_msg = f"Error making meshes single-sided: {UnicodeHelper.safe_str(e)}"
            logger.error(error_msg)
            self._status_label.text = f"Error: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}"

    def on_shutdown(self) -> None:
        """Called when the extension is deactivated."""
        logger.info("=" * 50)
        logger.info("USD CLEANER EXTENSION SHUTDOWN")
        logger.info("=" * 50)

        if self._window:
            self._window.destroy()
            self._window = None
            logger.info("UI destroyed successfully")

        logger.info("Extension shutdown completed")
        logger.info("=" * 50)
