from types import UnionType

import bpy
from blender_nerf_tools.blender_utility.logging_utility import log_report
from blender_nerf_tools.blender_utility.object_utility import (
    add_collection,
    add_cube,
    add_empty,
    get_collection,
    get_object
)
from blender_nerf_tools.constants import (
    AABB_BOX_ID,
    AABB_IS_CUBE_DEFAULT,
    AABB_IS_CUBE_ID,
    AABB_MAX_DEFAULT,
    AABB_MAX_ID,
    AABB_MIN_DEFAULT,
    AABB_MIN_ID,
    CAMERA_NEAR_ID,
    GLOBAL_TRANSFORM_ID,
    MAIN_COLLECTION_ID,
    NERF_PROPS_ID,
    TIME_DEFAULT,
    TIME_ID,
    TRAINING_STEPS_DEFAULT,
    TRAINING_STEPS_ID,
)

class NeRFScene:
    @classmethod
    def main_collection(cls):
        collection = get_collection(MAIN_COLLECTION_ID)
        return collection
    
    @classmethod
    def create_main_collection(cls):
        collection = cls.main_collection()
        if collection is None:
            collection = add_collection(MAIN_COLLECTION_ID)
        return collection

    # GLOBAL TRANSFORM

    @classmethod
    def global_transform(cls):
        return get_object(GLOBAL_TRANSFORM_ID)
    
    @classmethod
    def create_global_transform(cls):
        collection = cls.main_collection()
        obj = cls.global_transform()
        if obj is None:
            obj = add_empty(GLOBAL_TRANSFORM_ID, collection)
        if not obj.name in collection.objects:
            cls.main_collection().objects.link(obj)
        return obj
    
    # SETUP

    @classmethod
    def setup(cls):
        cls.create_main_collection()
        cls.create_nerf_props()
        cls.create_aabb_box()
        cls.create_global_transform()

    @classmethod
    def is_setup(cls):
        return (
            cls.main_collection() is not None
            and cls.aabb_box() is not None
            and cls.global_transform() is not None
            and cls.nerf_props() is not None
        )

    # AABB BOX

    @classmethod
    def create_aabb_box(cls):
        collection = cls.main_collection()
        obj = cls.aabb_box()
        if obj is None:
            obj = add_cube(AABB_BOX_ID, collection)
            obj.display_type = 'BOUNDS'
            bpy.ops.object.modifier_add(type='WIREFRAME')
            
            # Set up custom AABB min prop
            obj[AABB_MIN_ID] = AABB_MIN_DEFAULT
            prop = obj.id_properties_ui(AABB_MIN_ID)
            prop.update(precision=5)

            # Set up custom AABB max prop
            obj[AABB_MAX_ID] = AABB_MAX_DEFAULT
            prop = obj.id_properties_ui(AABB_MAX_ID)
            prop.update(precision=5)

            # Set up custom AABB "is cubical" prop
            obj[AABB_IS_CUBE_ID] = AABB_IS_CUBE_DEFAULT

            # Helper method for adding min/max vars to a driver
            def add_min_max_vars(driver: bpy.types.Driver, axis: int):
                axis_name = ["x", "y", "z"][axis]
                
                vmin = driver.variables.new()
                vmin.name = f"{axis_name}_min"
                vmin.targets[0].id = obj
                vmin.targets[0].data_path = f"[\"{AABB_MIN_ID}\"][{axis}]"

                vmax = driver.variables.new()
                vmax.name = f"{axis_name}_max"
                vmax.targets[0].id = obj
                vmax.targets[0].data_path = f"[\"{AABB_MAX_ID}\"][{axis}]"

            # Set up drivers for location
            [px, py, pz] = [fc.driver for fc in obj.driver_add("location")]

            add_min_max_vars(px, 0)
            px.expression = "0.5 * (x_min + x_max)"

            add_min_max_vars(py, 1)
            py.expression = "0.5 * (y_min + y_max)"

            add_min_max_vars(pz, 2)
            pz.expression = "0.5 * (z_min + z_max)"
            
            # Set up drivers for scale
            [sx, sy, sz] = [fc.driver for fc in obj.driver_add("scale")]

            add_min_max_vars(sx, 0)
            sx.expression = "x_max - x_min"

            add_min_max_vars(sy, 1)
            sy.expression = "y_max - y_min"

            add_min_max_vars(sz, 2)
            sz.expression = "z_max - z_min"
        
        if not obj.name in collection.objects:
            collection.objects.link(obj)
        
        return obj

    @classmethod
    def aabb_box(cls):
        return get_object(AABB_BOX_ID)
    
    @classmethod
    def get_aabb_min(cls):
        return cls.aabb_box()[AABB_MIN_ID]
    
    @classmethod
    def set_aabb_min(cls, value):
        aabb_max = cls.get_aabb_max()
        if cls.get_is_aabb_cubical():
            aabb_size_half = 0.5 * (aabb_max[0] - value[0])
            aabb_center = cls.get_aabb_center()
            value = [aabb_center[i] - aabb_size_half for i in range(3)]
        safe_min = [min(value[i], aabb_max[i]) for i in range(3)]
        cls.aabb_box()[AABB_MIN_ID] = safe_min
        cls.update_aabb_box_drivers()

    @classmethod
    def get_aabb_max(cls):
        return cls.aabb_box()[AABB_MAX_ID]
    
    @classmethod
    def set_aabb_max(cls, value):
        aabb_min = cls.get_aabb_min()
        if cls.get_is_aabb_cubical():
            aabb_size_half = 0.5 * (value[0] - aabb_min[0])
            aabb_center = cls.get_aabb_center()
            value = [aabb_center[i] + aabb_size_half for i in range(3)]
        safe_max = [max(value[i], aabb_min[i]) for i in range(3)]
        cls.aabb_box()[AABB_MAX_ID] = safe_max
        cls.update_aabb_box_drivers()

    @classmethod
    def get_aabb_size(cls):
        max = cls.get_aabb_max()
        min = cls.get_aabb_min()
        return [max[i] - min[i] for i in range(3)]
    
    @classmethod
    def set_aabb_size(cls, value):
        center = cls.get_aabb_center()
        if cls.get_is_aabb_cubical():
            value = [value[0], value[0], value[0]]
        
        safe_size = [max(0, value[i]) for i in range(3)]

        aabb_box = cls.aabb_box()
        aabb_box[AABB_MAX_ID] = [center[i] + 0.5 * safe_size[i] for i in range(3)]
        aabb_box[AABB_MIN_ID] = [center[i] - 0.5 * safe_size[i] for i in range(3)]
        cls.update_aabb_box_drivers()
    
    @classmethod
    def get_aabb_center(cls):
        max = cls.get_aabb_max()
        min = cls.get_aabb_min()
        return [0.5 * (max[i] + min[i]) for i in range(3)]
    
    @classmethod
    def set_aabb_center(cls, value):
        size = cls.get_aabb_size()
        
        aabb_box = cls.aabb_box()
        aabb_box[AABB_MAX_ID] = [value[i] + 0.5 * size[i] for i in range(3)]
        aabb_box[AABB_MIN_ID] = [value[i] - 0.5 * size[i] for i in range(3)]
        cls.update_aabb_box_drivers()
    
    @classmethod
    def get_is_aabb_cubical(cls) -> bool:
        return cls.aabb_box()[AABB_IS_CUBE_ID]
    
    @classmethod
    def set_is_aabb_cubical(cls, value: bool):
        if value is True:
            new_size = cls.get_aabb_size()[0]
            cls.set_aabb_size([new_size, new_size, new_size])
        cls.aabb_box()[AABB_IS_CUBE_ID] = value
    
    @classmethod
    def update_aabb_box_drivers(cls):
        obj = cls.aabb_box()
        # dirty hack - re-evaluates drivers (thank you https://blenderartists.org/t/driver-update-dependencies-via-script/1126347)
        for driver in obj.animation_data.drivers:
            orig_expr = driver.driver.expression
            # add a space to the expression, then remove it
            driver.driver.expression = f"{orig_expr} "
            driver.driver.expression = orig_expr
    
    # NERF PROPERTIES

    @classmethod
    def create_nerf_props(cls):
        collection = cls.main_collection()
        obj = cls.nerf_props()
        
        if obj == None:
            obj = add_empty(NERF_PROPS_ID, collection)
            
            obj[TRAINING_STEPS_ID] = TRAINING_STEPS_DEFAULT

            obj[TIME_ID] = TIME_DEFAULT
            prop_mgr = obj.id_properties_ui(TIME_ID)
            prop_mgr.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
        
        if not obj.name in collection.objects:
            collection.objects.link(obj)
    
    @classmethod
    def nerf_props(cls):
        return get_object(NERF_PROPS_ID)

    @classmethod
    def get_nerf_prop(cls, prop_id):
        if prop_id in cls.nerf_props():
            return cls.nerf_props()[prop_id]
        else:
            return None
    
    @classmethod
    def set_training_steps(cls, value: int):
        cls.nerf_props()[TRAINING_STEPS_ID] = value
    
    @classmethod
    def get_training_steps(cls):
        return cls.nerf_props()[TRAINING_STEPS_ID]
    
    @classmethod
    def get_time(cls):
        return cls.get_nerf_prop(TIME_ID)
    
    # CAMERA SELECTION

    @classmethod
    def is_nerf_camera(cls, obj):
        # TODO: stricter check
        return obj.type == 'CAMERA'

    @classmethod
    def get_selected_cameras(cls):
        return [obj for obj in bpy.context.selected_objects if cls.is_nerf_camera(obj)]
    
    @classmethod
    def get_all_cameras(cls):
        return [obj for obj in bpy.data.objects if cls.is_nerf_camera(obj)]
    
    @classmethod
    def select_all_cameras(cls):
        for obj in cls.get_all_cameras():
            obj.select_set(True)
    
    @classmethod
    def deselect_all_cameras(cls):
        bpy.ops.object.select_all(action='DESELECT')

    @classmethod
    def set_selected_camera(cls, camera, change_view = True):
        camera.select_set(True)
        bpy.context.view_layer.objects.active = camera
        if change_view:
            cls.set_view_from_camera(camera)

    @classmethod
    def select_camera_with_offset(cls, offset):
        selected_cameras = cls.get_selected_cameras()
        NeRFScene.deselect_all_cameras()
        if len(selected_cameras) == 1:
            current_camera = selected_cameras[0]
            all_cameras = cls.get_all_cameras()
            current_camera_index = all_cameras.index(current_camera)
            target_camera = all_cameras[(current_camera_index + offset) % len(all_cameras)]
            cls.set_selected_camera(target_camera)

    @classmethod
    def select_previous_camera(cls):
        cls.select_camera_with_offset(-1)
    
    @classmethod
    def select_next_camera(cls):
        cls.select_camera_with_offset(1)
    
    @classmethod
    def select_first_camera(cls):
        selected_cameras = cls.get_selected_cameras()
        NeRFScene.deselect_all_cameras()
        if len(selected_cameras) > 1:
            cls.set_selected_camera(selected_cameras[0])
        else:
            cls.set_selected_camera(cls.get_all_cameras()[0])

    @classmethod
    def select_last_camera(cls):
        selected_cameras = cls.get_selected_cameras()
        NeRFScene.deselect_all_cameras()
        if len(selected_cameras) > 1:
            cls.set_selected_camera(selected_cameras[-1])
        else:
            cls.set_selected_camera(cls.get_all_cameras()[-1])

    @classmethod
    def select_cameras_in_radius(cls, radius):
        cls.deselect_all_cameras()
        for camera in cls.get_all_cameras():
            dist_to_cursor = (camera.location - bpy.context.scene.cursor.location).length
            if dist_to_cursor <= radius:
                camera.select_set(True)

    @classmethod
    def set_active_camera(cls, camera):
        bpy.context.scene.camera = camera

    @classmethod
    def set_view_from_camera(cls, camera):
        bpy.context.scene.camera = camera
        # thank you https://blender.stackexchange.com/a/30645/141797
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].region_3d.view_perspective = 'CAMERA'
                break
    
    # CAMERA PROPERTIES

    @classmethod
    def set_camera_near(cls, camera, value):
        camera[CAMERA_NEAR_ID] = value
    
    @classmethod
    def get_camera_near(cls, camera):
        return camera[CAMERA_NEAR_ID]
