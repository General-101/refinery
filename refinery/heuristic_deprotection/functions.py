#
# This file is part of Refinery.
#
# For authors and copyright check AUTHORS.TXT
#
# Refinery is free software under the GNU General Public License v3.0.
# See LICENSE for more information.
#

from reclaimer.enums import materials_list, material_effect_types
from refinery.heuristic_deprotection.constants import *
from refinery.heuristic_deprotection.util import MinPriority, sanitize_name,\
     sanitize_name_piece, get_tag_id, join_names, get_model_name,\
     get_sound_sub_dir_and_name, get_sound_looping_name, get_sound_scenery_name,\
     sanitize_model_or_sound_name
from traceback import format_exc


def heuristic_deprotect(tag_id, halo_map, tag_path_handler,
                        root_dir="", sub_dir="", name="", **kw):
    if tag_id is None:
        return INF

    tag_index_id = tag_id & 0xFFff
    if tag_index_id not in range(len(halo_map.tag_index.tag_index)):
        return INF

    # create a copy of this set for each recursion level to prevent
    # infinite recursion, but NOT prevent revisiting the
    seen = kw.setdefault("seen", set())
    kw.setdefault("depth", INF)
    priority = kw.get("priority")

    min_priority = MinPriority()
    curr_min_prio = tag_path_handler.get_priority_min(tag_index_id)
    if tag_index_id in seen or kw["depth"] < 0:
        # do nothing if tag already seen or already at max depth
        return curr_min_prio
    elif not kw.get("use_minimum_priorities") or priority is None or curr_min_prio < priority:
        pass
    elif curr_min_prio > priority or (kw.get("use_minimum_equal_priorities") and 
                                      kw.get("return_on_equal_min_priority")):
        # do nothing if priority is lower than the lowest priority
        # of any tag referenced by this tag or its dependencies, or
        # is equal and return_on_equal_min_priority is True
        return curr_min_prio

    kw.update(depth=kw["depth"] - 1, min_priority=min_priority)
    seen.add(tag_index_id)

    rename_func = recursive_rename_functions.get(
        halo_map.tag_index.tag_index[tag_index_id].class_1.enum_name)
    if rename_func:
        try:
            rename_func(tag_id, halo_map, tag_path_handler,
                        root_dir, sub_dir, name, **kw)
        except Exception:
            print(format_exc())
    else:
        min_priority.val = tag_path_handler.set_path_by_priority(
            tag_id, root_dir + sub_dir + name, priority,
            kw.get("override"), kw.get("do_printout"))

    # remove the tag_id so this tag can be revisited by higher up references
    seen.remove(tag_index_id)
    tag_path_handler.set_priority_min(tag_index_id, min_priority.val)
    return min_priority.val


def rename_scnr(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = levels_dir

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id, reextract=True)
    if meta is None:
        return
    elif not name:
        name = sanitize_name(halo_map.map_header.map_name)

    level_dir = sub_dir + '%s\\' % name

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + level_dir + name, INF,
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw_no_priority = dict(kw)
    kw_no_priority.pop("priority", None)

    # rename the open sauce stuff
    try:
        min_prio.val = heuristic_deprotect(
            get_tag_id(meta.project_yellow_definitions),
            priority=INF, name=name, sub_dir=sub_dir + globals_dir,
            **kw_no_priority)
    except AttributeError:
        pass

    # rename the references at the bottom of the scenario tag
    tag_path_handler.set_path_by_priority(
        get_tag_id(meta.custom_object_names), sub_dir + "object_names", INF,
        kw.get("override"), kw.get("do_printout"))

    tag_path_handler.set_path_by_priority(
        get_tag_id(meta.ingame_help_text), sub_dir + "help_text", INF,
        kw.get("override"), kw.get("do_printout"))

    tag_path_handler.set_path_by_priority(
        get_tag_id(meta.hud_messages), sub_dir + "hud_messages", INF,
        kw.get("override"), kw.get("do_printout"))

    # rename sky references
    for b in meta.skies.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.sky), sub_dir=sky_dir + name + "\\",
            name=name + " sky", **kw)

    palette_renames = (
        ("machines_palette", machines_dir),
        ("controls_palette", controls_dir),
        ("light_fixtures_palette", light_fixtures_dir),
        ("sound_sceneries_palette", sfx_emitters_dir),
        ("sceneries_palette", scenery_dir),
        ("actors_palette", characters_dir),
        ("bipeds_palette", characters_dir),
        ("vehicles_palette", vehicles_dir),
        ("equipments_palette", powerups_dir),
        ("weapons_palette", weapons_dir)
        )

    # rename player starting weapon references
    for profile in meta.player_starting_profiles.STEPTREE:
        start_name = sanitize_name(profile.name)
        if not start_name:
            start_name = "start weapon"

        min_prio.val = heuristic_deprotect(get_tag_id(profile.primary_weapon),
                         sub_dir=weapons_dir, name=start_name + " pri", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(profile.secondary_weapon),
                         sub_dir=weapons_dir, name=start_name + " sec", **kw)

    local_item_coll_dir = sub_dir + item_coll_dir

    # rename detail objects palette
    for b in meta.detail_object_collection_palette.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.name), sub_dir=sub_dir + "detail objects\\",
            priority=MEDIUM_PRIORITY, **kw_no_priority)

    # rename decal palette references
    for swatch in meta.decals_palette.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(swatch.name), priority=MEDIUM_PRIORITY,
                         sub_dir=sub_dir + "decals\\", **kw_no_priority)

    # rename palette references
    for b_name, pal_sub_dir in palette_renames:
        for swatch in meta[b_name].STEPTREE:
            min_prio.val = heuristic_deprotect(get_tag_id(swatch.name), priority=MEDIUM_PRIORITY,
                             sub_dir=pal_sub_dir, **kw_no_priority)

    # netgame flags
    for b in meta.netgame_flags.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.weapon_group), sub_dir=local_item_coll_dir,
            name="ng flag", priority=MEDIUM_PRIORITY, **kw_no_priority)

    # netgame equipment
    for b in meta.netgame_equipments.STEPTREE:
        ng_name = ""
        ng_coll_meta = halo_map.get_meta(get_tag_id(b.item_collection))
        if hasattr(ng_coll_meta, "item_permutations"):
            item_names = []
            for item in ng_coll_meta.item_permutations.STEPTREE:
                item_name = tag_path_handler.get_basename(get_tag_id(item.item))
                if item_name:
                    item_names.append(item_name)

            ng_name = join_names(sorted(item_names), 96)

        if not ng_name:
            ng_name = "ng equipment"

        min_prio.val = heuristic_deprotect(
            get_tag_id(b.item_collection), sub_dir=local_item_coll_dir,
            name=ng_name, priority=MEDIUM_PRIORITY, **kw_no_priority)

    # starting equipment
    # do this AFTER netgame equipment
    i = 0
    for b in meta.starting_equipments.STEPTREE:
        j = 0
        for k in range(1, 7):
            min_prio.val = heuristic_deprotect(
                get_tag_id(b['item_collection_%s' % k]),
                sub_dir=local_item_coll_dir + "start equipment\\",
                priority=MEDIUM_PRIORITY, **kw_no_priority)
            j += 1
        i += 1

    # rename animation references
    for b in meta.ai_animation_references.STEPTREE:
        anim_name = sanitize_name(b.animation_name)
        if not anim_name:
            anim_name = "ai anim"

        min_prio.val = heuristic_deprotect(
            get_tag_id(b.animation_graph), name=anim_name,
            sub_dir=cinematics_dir + "animations\\",
            priority=LOW_PRIORITY, **kw_no_priority)

    # rename bsp references
    i = 0
    for b in meta.structure_bsps.STEPTREE:
        bsp_name = name
        if len(meta.structure_bsps.STEPTREE) > 1:
            bsp_name += " %s" % i

        min_prio.val = heuristic_deprotect(
            get_tag_id(b.structure_bsp), priority=SCNR_BSPS_PRIORITY,
            sub_dir=sub_dir, name=bsp_name, **kw_no_priority)
        i += 1

    # rename bsp modifiers
    bsp_modifiers = getattr(getattr(meta, "bsp_modifiers", ()), "STEPTREE", ())
    for modifier in bsp_modifiers:
        try:
            bsp_name = tag_path_handler.get_basename(
                get_tag_id(
                    meta.structure_bsps.STEPTREE[b.bsp_index].structure_bsp))
        except Exception:
            bsp_name = ""

        lightmap_sub_dir = sub_dir + (bsp_name + " lightmaps\\").strip()
        for b in modifier.lightmap_sets.STEPTREE:
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.std_lightmap), priority=VERY_HIGH_PRIORITY,
                sub_dir=lightmap_sub_dir, name=b.name + " std", **kw_no_priority)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.dir_lightmap_1), priority=VERY_HIGH_PRIORITY,
                sub_dir=lightmap_sub_dir, name=b.name + " dlm1", **kw_no_priority)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.dir_lightmap_2), priority=VERY_HIGH_PRIORITY,
                sub_dir=lightmap_sub_dir, name=b.name + " dlm2", **kw_no_priority)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.dir_lightmap_3), priority=VERY_HIGH_PRIORITY,
                sub_dir=lightmap_sub_dir, name=b.name + " dlm3", **kw_no_priority)

        sky_set_dir = sub_dir + (bsp_name + " sky sets\\").strip()
        for sky_set in modifier.sky_sets.STEPTREE:
            for b in sky_set.skies.STEPTREE:
                min_prio.val = heuristic_deprotect(
                    get_tag_id(b.sky), sub_dir=sky_set_dir,
                    name=sky_set.name, **kw)

    # rename ai conversation sounds
    i = 0
    conv_dir = sub_dir + "ai convos\\"
    for b in meta.ai_conversations.STEPTREE:
        j = 0
        conv_name = sanitize_name(b.name)
        if not conv_name:
            conv_name = " conv %s" % i

        for b in b.lines.STEPTREE:
            line = conv_name + " line %s " % j
            for k in range(1, 7):
                min_prio.val = heuristic_deprotect(
                    get_tag_id(b['variant_%s' % k]), sub_dir=conv_dir,
                    priority=MEDIUM_PRIORITY, name=line.strip(), **kw_no_priority)
            j += 1
        i += 1

    # rename tag references
    for b in meta.references.STEPTREE:
        kw['priority'] = LOW_PRIORITY
        sub_id = get_tag_id(b.reference)
        tag_cls = b.reference.tag_class.enum_name
        tag_name = "protected_%s" % sub_id

        if tag_cls == "model_animations":
            ref_sub_dir = cinematic_anims_dir
        elif tag_cls == "effect":
            ref_sub_dir = cinematic_effects_dir
        elif tag_cls == "biped":
            ref_sub_dir = cinematics_dir + characters_dir
        elif tag_cls == "vehicle":
            ref_sub_dir = cinematics_dir + vehicles_dir
        elif tag_cls == "weapon":
            ref_sub_dir = cinematics_dir + weapons_dir
        elif tag_cls == "projectile":
            ref_sub_dir = cinematics_dir + projectiles_dir
        elif tag_cls == "garbage":
            ref_sub_dir = cinematics_dir + garbage_dir
        elif tag_cls == "equipment":
            ref_sub_dir = cinematics_dir + powerups_dir
        elif tag_cls == "scenery":
            ref_sub_dir = cinematics_dir + scenery_dir
        elif tag_cls == "sound_scenery":
            ref_sub_dir = cinematics_dir + sfx_emitters_dir
        elif "device" in tag_cls:
            ref_sub_dir = (cinematics_dir + (
                tag_cls.lstrip("device_").replace("_", " ") + "s\\"))
        elif tag_cls == "sound_looping":
            ref_sub_dir = sub_dir + "music\\"
        elif tag_cls == "sound":
            snd_meta = halo_map.get_meta(sub_id, ignore_rawdata=True)
            ref_sub_dir = sub_dir + "sounds\\"
            if snd_meta is None:
                continue
            new_ref_sub_dir, new_tag_name = get_sound_sub_dir_and_name(
                snd_meta, ref_sub_dir, tag_name)
            if tag_name != new_tag_name:
                kw['priority'] = DEFAULT_PRIORITY
            ref_sub_dir, tag_name = new_ref_sub_dir, new_tag_name

        else:
            ref_sub_dir = sub_dir + "referenced tags\\"

        min_prio.val = heuristic_deprotect(sub_id, sub_dir=ref_sub_dir, **kw)


def rename_matg(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = globals_dir

    kw.setdefault("priority", MEDIUM_PRIORITY)
    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    kwargs_no_priority = dict(kw)
    kwargs_no_priority.pop('priority')

    meta = halo_map.get_meta(tag_id, reextract=True)
    if meta is None:
        return
    elif not name:
        name = 'globals'

    # rename this globals tag
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    for i in range(len(meta.sounds.STEPTREE)):
        water_name = {0:"enter_water", 1:"exit_water"}.get(i, "unknown")
        min_prio.val = heuristic_deprotect(
            get_tag_id(meta.sounds.STEPTREE[i].sound), priority=INF,
            sub_dir="sound\\sfx\\impulse\\coolant\\", name=water_name,
            **kwargs_no_priority)

    for b in meta.cameras.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.camera), priority=INF, sub_dir=sub_dir,
            name="default unit camera track", **kwargs_no_priority)

    i = 0
    for b in meta.grenades.STEPTREE:
        g_dir = weapons_dir + "grenade %s\\" % i
        g_name = "grenade %s" % i

        eqip_tag_id = get_tag_id(b.equipment)
        g_priority = 1.5
        min_prio.val = heuristic_deprotect(eqip_tag_id, sub_dir=g_dir, name=g_name,
                         priority=g_priority, **kwargs_no_priority)
        if eqip_tag_id is not None:
            g_dir = tag_path_handler.get_sub_dir(eqip_tag_id, root_dir)
            g_name = tag_path_handler.get_basename(eqip_tag_id)
            g_priority = tag_path_handler.get_priority(eqip_tag_id)

        min_prio.val = heuristic_deprotect(get_tag_id(b.throwing_effect), sub_dir=g_dir,
                         name=g_name + " throw", priority=g_priority,
                         **kwargs_no_priority)
        min_prio.val = heuristic_deprotect(get_tag_id(b.hud_interface), sub_dir=g_dir,
                         name=g_name + " hud", priority=g_priority,
                         **kwargs_no_priority)
        min_prio.val = heuristic_deprotect(get_tag_id(b.projectile), sub_dir=g_dir,
                         name=g_name + " projectile", priority=g_priority,
                         **kwargs_no_priority)
        i += 1

    rast_kwargs = dict(kw)
    exp_tex_kwargs = dict(kw)
    rast_kwargs.update(priority=INF, sub_dir=rasterizer_dir)
    exp_tex_kwargs.update(priority=INF, sub_dir="levels\\a10\\bitmaps\\")
    for b in meta.rasterizer_datas.STEPTREE:
        func_tex = b.function_textures
        def_tex = b.default_textures
        exp_tex = b.experimental_textures
        vid_eff_tex = b.video_effect_textures

        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.distance_attenuation),
            name="distance attenuation", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.vector_normalization),
            name="vector normalization", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.atmospheric_fog_density),
            name="atmospheric fog density", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.planar_fog_density),
            name="planar fog density", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.linear_corner_fade),
            name="linear corner fade", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.active_camouflage_distortion),
            name="active camouflage distortion", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(func_tex.glow), name="glow", **rast_kwargs)

        min_prio.val = heuristic_deprotect(
            get_tag_id(def_tex.default_2d), name="default 2d", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(def_tex.default_3d), name="default 3d", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(def_tex.default_cubemap),
            name="default cube map", **rast_kwargs)

        min_prio.val = heuristic_deprotect(
            get_tag_id(exp_tex.test0), name="water_ff", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(exp_tex.test1), name="cryo glass", **exp_tex_kwargs)

        min_prio.val = heuristic_deprotect(
            get_tag_id(vid_eff_tex.video_scanline_map),
            name="video mask", **rast_kwargs)
        min_prio.val = heuristic_deprotect(
            get_tag_id(vid_eff_tex.video_noise_map),
            name="video noise", **rast_kwargs)

    old_tags_kwargs = dict(kw)
    ui_bitm_kwargs = dict(kw)
    old_tags_kwargs.update(priority=VERY_HIGH_PRIORITY,
                           sub_dir="old tags\\")
    ui_bitm_kwargs.update(priority=VERY_HIGH_PRIORITY,
                          sub_dir=ui_hud_dir + "bitmaps\\")
    for b in meta.interface_bitmaps.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.font_system), sub_dir=ui_dir,
                         name="system font", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.font_terminal), sub_dir=ui_dir,
                         name="terminal font", **kw)

        min_prio.val = heuristic_deprotect(get_tag_id(b.hud_globals),
                         sub_dir=ui_hud_dir, name="default", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.hud_digits_definition),
                         sub_dir=ui_hud_dir, name="counter", **kw)

        min_prio.val = heuristic_deprotect(get_tag_id(b.screen_color_table),
                         name="internal screen", **old_tags_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.hud_color_table),
                         name="internal hud", **old_tags_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.editor_color_table),
                         name="internal editor", **old_tags_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.dialog_color_table),
                         name="internal dialog", **old_tags_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.localization),
                         name="internal string localization", **old_tags_kwargs)

        min_prio.val = heuristic_deprotect(get_tag_id(b.motion_sensor_sweep_bitmap),
                         name="hud_sweeper", **ui_bitm_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.motion_sensor_sweep_bitmap_mask),
                         name="hud_sweeper_mask", **ui_bitm_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.multiplayer_hud_bitmap),
                         name="hud_multiplayer", **ui_bitm_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.motion_sensor_blip),
                         name="hud_sensor_blip", **ui_bitm_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.interface_goo_map1),
                         name="hud_sensor_blip_custom", **ui_bitm_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.interface_goo_map2),
                         name="hud_msg_icons_sm", **ui_bitm_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.interface_goo_map3),
                         sub_dir="characters\\jackal\\bitmaps\\",
                         name="shield noise", **kw)

    for b in meta.multiplayer_informations.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.flag), name="flag",
                         sub_dir="weapons\\flag\\", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.ball), name="ball",
                         sub_dir="weapons\\ball\\", **kw)

        min_prio.val = heuristic_deprotect(get_tag_id(b.hill_shader), name="hilltop",
                         sub_dir="scenery\\hilltop\\shaders\\", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.flag_shader), name="flag_blue",
                         sub_dir="weapons\\flag\\shaders\\", **kw)

        min_prio.val = heuristic_deprotect(get_tag_id(b.unit), name="player_mp",
                         priority=VERY_HIGH_PRIORITY,
                         sub_dir="characters\\player_mp\\", **kwargs_no_priority)

        for multiplayer_sound in b.sounds.STEPTREE:
            min_prio.val = heuristic_deprotect(get_tag_id(multiplayer_sound.sound),
                             sub_dir="sound\\dialog\\announcer\\", **kw)

    for b in meta.player_informations.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.unit), name="player_sp",
                         priority=VERY_HIGH_PRIORITY,
                         sub_dir="characters\\player_sp\\", **kwargs_no_priority)
        min_prio.val = heuristic_deprotect(get_tag_id(b.coop_respawn_effect),
                         priority=VERY_HIGH_PRIORITY, sub_dir=effects_dir,
                         name="coop teleport", **kwargs_no_priority)

    for b in meta.first_person_interfaces.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.first_person_hands),
                         sub_dir="characters\\player_sp\\fp\\", name="fp",
                         priority=VERY_HIGH_PRIORITY, **kwargs_no_priority)
        min_prio.val = heuristic_deprotect(get_tag_id(b.base_bitmap),
                         name="hud_health_base", **ui_bitm_kwargs)

        min_prio.val = heuristic_deprotect(get_tag_id(b.shield_meter), sub_dir=ui_hud_dir,
                         name="cyborg shield", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.body_meter), sub_dir=ui_hud_dir,
                         name="cyborg body", **kw)

        min_prio.val = heuristic_deprotect(get_tag_id(b.night_vision_toggle_on_effect),
                         sub_dir=sfx_weapons_dir, name="night_vision_on",
                         **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.night_vision_toggle_off_effect),
                         sub_dir=sfx_weapons_dir, name="night_vision_off",
                         **kw)

    fall_kwargs = dict(kw)
    fall_kwargs.update(priority=VERY_HIGH_PRIORITY, sub_dir=sub_dir)
    for b in meta.falling_damages.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.falling_damage),
                         name="falling", **fall_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.distance_damage),
                         name="distance", **fall_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.vehicle_environment_collision_damage),
                         name="vehicle_hit_environment", **fall_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.vehicle_killed_unit_damage),
                         name="vehicle_killed_unit", **fall_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.vehicle_collision_damage),
                         name="vehicle_collision", **fall_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.flaming_death_damage),
                         name="flaming_death", **fall_kwargs)

    i = 0
    mats_kwargs = dict(kw)
    mats_kwargs["priority"] = VERY_HIGH_PRIORITY
    for b in meta.materials.STEPTREE:
        mat_name = "unknown" if i not in range(len(materials_list)) else materials_list[i]
        min_prio.val = heuristic_deprotect(get_tag_id(b.sound), name=mat_name,
                         sub_dir="sound\\sfx\\impulse\\", **mats_kwargs)
        min_prio.val = heuristic_deprotect(get_tag_id(b.melee_hit_sound), name=mat_name,
                         sub_dir="sound\\sfx\\impulse\\melee\\", **mats_kwargs)

        for particle_effect in b.particle_effects.STEPTREE:
            min_prio.val = heuristic_deprotect(get_tag_id(particle_effect.particle_type),
                             sub_dir="effects\\particles\\solid\\",
                             name="%s breakable" % mat_name, **mats_kwargs)
        i += 1


def rename_hudg(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir=ui_hud_dir, name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir:
        sub_dir = ui_hud_dir
    if not name:
        name = "default"

    kw.setdefault('priority', MEDIUM_HIGH_PRIORITY)
    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id, reextract=True)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    msg_param = meta.messaging_parameters
    min_prio.val = heuristic_deprotect(
        get_tag_id(msg_param.single_player_font),
        sub_dir=ui_dir, name="font sp", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(msg_param.multi_player_font),
        sub_dir=ui_dir, name="font mp", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(msg_param.item_message_text),
        sub_dir=ui_hud_dir, name="hud item messages", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(msg_param.alternate_icon_text),
        sub_dir=ui_hud_dir, name="hud icon messages", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(msg_param.icon_bitmap),
        sub_dir=ui_hud_dir + bitmaps_dir, name="hud msg icons", **kw)

    tag_path_handler.set_path_by_priority(
         get_tag_id(meta.hud_messages), sub_dir + "hud_messages", INF,
         kw.get("override"), kw.get("do_printout"))

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.waypoint_parameters.arrow_bitmaps),
        sub_dir=ui_hud_dir + bitmaps_dir + "combined\\",
        name="hud waypoints", **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.hud_globals.default_weapon_hud),
        sub_dir=ui_hud_dir, name="empty", **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.hud_damage_indicators.indicator_bitmap),
        sub_dir=ui_hud_dir + bitmaps_dir + "combined\\",
        name="hud damage arrows", **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.carnage_report_bitmap),
        sub_dir=ui_shell_dir + bitmaps_dir,
        name="postgame carnage report", **kw)


def rename_sbsp(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    kw.setdefault("priority", MEDIUM_PRIORITY if
                  sub_dir else DEFAULT_PRIORITY)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.lightmap_bitmaps),
                     sub_dir=sub_dir, name=name, **kw)

    coll_shdr_dir     = sub_dir + "shaders collidable\\"
    non_coll_shdr_dir = sub_dir + "shaders non collidable\\"
    override = kw.pop("override", None)
    # collision materials
    for b in meta.collision_materials.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.shader), sub_dir=coll_shdr_dir,
            name="protected_%s" % get_tag_id(b.shader),
            override=True, **kw)

    # lightmap materials(non-collidable)
    kw["override"] = override
    for lightmap in meta.lightmaps.STEPTREE:
        for mat in lightmap.materials.STEPTREE:
            min_prio.val = heuristic_deprotect(
                get_tag_id(mat.shader), sub_dir=non_coll_shdr_dir,
                name="protected_%s" % get_tag_id(mat.shader), **kw)

    # lens flares
    for b in meta.lens_flares.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.shader), sub_dir=sub_dir + "lens flares\\",
            name="protected_%s" % get_tag_id(b.shader), **kw)

    # fog palettes
    for b in meta.fog_palettes.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.fog), sub_dir=sub_dir + weather_dir,
                         name=sanitize_name_piece(b.name, "protected_%s" %
                                                  get_tag_id(b.fog)), **kw)

    # weather palettes
    for b in meta.weather_palettes.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.particle_system),
                         sub_dir=sub_dir + weather_dir,
                         name=sanitize_name_piece(
                             b.name, "protected_weather_%s" %
                             get_tag_id(b.particle_system)), **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.wind), sub_dir=sub_dir + weather_dir,
                         name=sanitize_name_piece(
                             b.name, "protected_wind_%s" %
                             get_tag_id(b.wind)), **kw)

    # background sounds
    for b in meta.background_sounds_palette.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.background_sound),
                         sub_dir=sub_dir + sounds_dir,
                         name=sanitize_name_piece(
                             b.name, "protected_bg_sound_%s" %
                             get_tag_id(b.background_sound)), **kw)

    # sound environments
    for b in meta.sound_environments_palette.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.sound_environment),
                         sub_dir=snd_sound_env_dir,
                         name=sanitize_name_piece(
                             b.name, "protected_sound_env_%s" %
                             get_tag_id(b.sound_environment)), **kw)


def rename_sky_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = sky_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return
    elif not name:
        name = 'sky'

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir, sub_dir=sub_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault("priority", DEFAULT_PRIORITY)

    for b in (meta.model, meta.animation_graph):
        min_prio.val = heuristic_deprotect(get_tag_id(b), name=name, **kw)

    for b in meta.lights.STEPTREE:
        light_name = sanitize_name(b.global_function_name)
        if not light_name:
            widget_name = "light"
        min_prio.val = heuristic_deprotect(get_tag_id(b.lens_flare), name=light_name, **kw)


def rename_obje(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    obje_attrs = meta.obje_attrs
    obje_type = obje_attrs.object_type.enum_name

    i = 1
    for f in obje_attrs.functions.STEPTREE:
        kw["func_%s_name" % i] = sanitize_name(f.usage).\
                                 replace(" source", "").replace(" src", "")
        i += 1

    string_name = model_name = ""
    if not name or name.startswith("protected"):
        if obje_type in ("weap", "eqip"):
            string_name = tag_path_handler.get_item_string(
                meta.item_attrs.message_index)
            eqip_attrs = getattr(meta, "eqip_attrs", None)
            if eqip_attrs and eqip_attrs.powerup_type.data in (1, 4):
                string_name = eqip_attrs.powerup_type.enum_name.replace("_", " ")

        elif obje_type == "vehi":
            string_name = tag_path_handler.get_icon_string(
                meta.obje_attrs.hud_text_message_index)

        model_tag_id = get_tag_id(obje_attrs.model)
        model_name = tag_path_handler.get_basename(model_tag_id)
        if not model_name or model_name.startswith("protected"):
            if obje_type == "ssce":
                model_name = get_sound_scenery_name(meta, halo_map, name)
            else:
                model_name = get_model_name(
                    halo_map=halo_map, tag_id=model_tag_id, name=name
                    )

    if kw.get("prioritize_model_names") and model_name:
        name = model_name
        kw.setdefault('priority', HIGH_PRIORITY)
    elif string_name:
        # up the priority if we could detect a name for
        # this in the strings for the weapon or vehicles
        name = string_name
        kw.setdefault('priority', HIGH_PRIORITY)
    elif not name:
        name = model_name or ("protected_%s" % tag_id)
        kw.setdefault('priority', MEDIUM_HIGH_PRIORITY)

    if obje_type == "bipd":
        obje_dir = characters_dir
    elif obje_type == "vehi":
        obje_dir = vehicles_dir
    elif obje_type == "weap":
        obje_dir = weapons_dir
    elif obje_type == "eqip":
        obje_dir = powerups_dir
    elif obje_type == "garb":
        obje_dir = garbage_dir
    elif obje_type == "proj":
        obje_dir = projectiles_dir
    elif obje_type == "scen":
        obje_dir = scenery_dir
    elif obje_type == "mach":
        obje_dir = machines_dir
    elif obje_type == "ctrl":
        obje_dir = controls_dir
    elif obje_type == "lifi":
        obje_dir = light_fixtures_dir
    elif obje_type == "plac":
        obje_dir = placeholders_dir
    elif obje_type == "ssce":
        obje_dir = sfx_emitters_dir
    else:
        obje_dir = ""

    if not sub_dir:
        sub_dir = obje_dir

    orig_sub_dir    = sub_dir
    is_obje_sub_dir = sub_dir.lower().endswith(obje_dir)
    if is_obje_sub_dir:
        sub_dir += name + "\\"

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'), kw.get("override"),
        kw.get("do_printout"))

    assigned_name = tag_path_handler.get_basename(tag_id)
    if name != assigned_name:
        name = assigned_name
        if is_obje_sub_dir:
            sub_dir = orig_sub_dir + name + "\\"

        min_prio.val = tag_path_handler.set_path_by_priority(
            tag_id, root_dir + sub_dir + name, kw.get('priority'), True,
            kw.get("do_printout"))

    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    if obje_type in ("weap", "eqip", "garb"):
        rename_item_attrs(meta, tag_id, sub_dir=sub_dir, name=name, **kw)
    elif obje_type in ("bipd", "vehi"):
        rename_unit_attrs(meta, tag_id, sub_dir=sub_dir, name=name, **kw)
    elif obje_type in ("mach", "ctrl", "lifi"):
        rename_devi_attrs(meta, tag_id, sub_dir=sub_dir, name=name, **kw)

    for b in (obje_attrs.model, obje_attrs.animation_graph,
              obje_attrs.collision_model, obje_attrs.physics):
        min_prio.val = heuristic_deprotect(get_tag_id(b), sub_dir=sub_dir, name=name, **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(obje_attrs.creation_effect),
        sub_dir=sub_dir + effects_dir, name="creation effect", **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(obje_attrs.modifier_shader),
        sub_dir=sub_dir + shaders_dir, name="modifier shader", **kw)

    for b in obje_attrs.attachments.STEPTREE:
        a_name = kw.get("func_%s_name" % b.primary_scale.data, "")
        if not a_name and b.type.tag_class.enum_name in ("contrail", "light"):
            a_name = b.marker.replace("\\", " ")
            if a_name: a_name += " "
            if b.type.tag_class.enum_name not in a_name.lower():
                a_name += b.type.tag_class.enum_name

        min_prio.val = heuristic_deprotect(
            get_tag_id(b.type), name=a_name,
            sub_dir=sub_dir + obje_effects_dir, **kw)

    for b in obje_attrs.widgets.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.reference), sub_dir=sub_dir + "widgets\\", **kw)

    proj_attrs = getattr(meta, "proj_attrs", None)
    if obje_type != "proj" or not proj_attrs:
        return

    min_prio.val = heuristic_deprotect(
        get_tag_id(proj_attrs.super_detonation),
        sub_dir=sub_dir + effects_dir, name="super detonation", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(proj_attrs.detonation.effect),
        sub_dir=sub_dir + effects_dir, name="detonation", **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(proj_attrs.physics.detonation_started),
        sub_dir=sub_dir + effects_dir, name="detonation started", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(proj_attrs.physics.flyby_sound),
        sub_dir=sub_dir + sound_dir, name="flyby sound", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(proj_attrs.physics.attached_detonation_damage),
        sub_dir=sub_dir, name="attached detonation", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(proj_attrs.physics.impact_damage),
        sub_dir=sub_dir, name="impact", **kw)

    i = 0
    for b in proj_attrs.material_responses.STEPTREE:
        if i >= len(materials_list):
            mat_name = "mat %s" % i
        else:
            mat_name = materials_list[i].replace("_", " ")

        min_prio.val = heuristic_deprotect(get_tag_id(b.effect),
                         sub_dir=sub_dir + "impact effects\\",
                         name=mat_name, **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.potential_response.effect),
                         sub_dir=sub_dir + "impact effects\\",
                         name="alt %s" % mat_name, **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.detonation_effect),
                         sub_dir=sub_dir + "impact effects\\",
                         name="detonation %s" % mat_name, **kw)
        i += 1


def rename_shdr(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = obje_shaders_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    shdr_type = meta.shdr_attrs.shader_type.enum_name
    func_name = ""
    if shdr_type == "smet":
        smet_attrs = meta.smet_attrs
        func_name = kw.get(
            "func_%s_name" % smet_attrs.external_function_sources.value.data, "")
    elif shdr_type == "spla":
        spla_attrs = meta.spla_attrs
        func_name = kw.get(
            "func_%s_name" % spla_attrs.intensity.source.data, "")

    if func_name and ("protected" in name or not name):
        name = func_name

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))

    name = tag_path_handler.get_basename(tag_id)
    bitmaps_sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    bitmaps_sub_dir = "\\".join(sub_dir.split("\\")[: -2])
    if bitmaps_sub_dir: bitmaps_sub_dir += "\\"
    bitmaps_sub_dir += bitmaps_dir

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  sub_dir=bitmaps_sub_dir, tag_path_handler=tag_path_handler)

    if shdr_type == "senv":
        senv_attrs = meta.senv_attrs
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.diffuse.base_map),
            name="%s_senv_diffuse" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.diffuse.primary_detail_map),
            name="%s_senv_pri_detail" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.diffuse.secondary_detail_map),
            name="%s_senv_sec_detail" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.diffuse.micro_detail_map),
            name="%s_senv_micro_detail" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.bump_properties.map),
            name="%s_senv_bump" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.self_illumination.map),
            name="%s_senv_self_illum" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(senv_attrs.reflection.cube_map),
            name="%s_senv_reflection" % name, **kw)

        senv_ext = getattr(getattr(senv_attrs, "os_shader_environment_ext", ()),
                           "STEPTREE", ())
        for b in senv_ext:
            min_prio.val = heuristic_deprotect(get_tag_id(b.specular_color_map),
                             name="%s_senv_spec_color" % name, **kw)


    elif shdr_type == "soso":
        soso_attrs = meta.soso_attrs
        min_prio.val = heuristic_deprotect(
            get_tag_id(soso_attrs.maps.diffuse_map),
            name="%s_soso_diffuse" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(soso_attrs.maps.multipurpose_map),
            name="%s_soso_multi" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(soso_attrs.maps.detail_map),
            name="%s_soso_detail" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(soso_attrs.reflection.cube_map),
            name="%s_soso_reflection" % name, **kw)
        soso_ext = getattr(getattr(soso_attrs, "os_shader_model_ext", ()),
                           "STEPTREE", ())
        for b in soso_ext:
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.specular_color_map),
                name="%s_soso_spec_color" % name, **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.base_normal_map),
                name="%s_soso_normal" % name, **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.detail_normal_1_map),
                name="%s_soso_normal_detail_1" % name, **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.detail_normal_2_map),
                name="%s_soso_normal_detail_2" % name, **kw)

    elif shdr_type in ("sotr", "schi", "scex"):
        if shdr_type == "scex":
            extra_layers = meta.scex_attrs.extra_layers
            maps_list = [meta.scex_attrs.four_stage_maps,
                         meta.scex_attrs.two_stage_maps]
        elif shdr_type == "schi":
            extra_layers = meta.schi_attrs.extra_layers
            maps_list = [meta.schi_attrs.maps]
        else:
            extra_layers = meta.sotr_attrs.extra_layers
            maps_list = [meta.sotr_attrs.maps]

        for maps in maps_list:
            for map in maps.STEPTREE:
                min_prio.val = heuristic_deprotect(get_tag_id(map.bitmap), name="%s_%s" %
                                 (name, shdr_type), **kw)

        kw.update(sub_dir=sub_dir)
        i = 0
        for extra_layer in extra_layers.STEPTREE:
            ex_layer_name = name
            if len(extra_layers.STEPTREE) == 1:
                ex_layer_name += "_ex_"
            else:
                ex_layer_name += "_ex_%s" % i
            min_prio.val = heuristic_deprotect(
                get_tag_id(extra_layer), name=ex_layer_name, **kw)
            i += 1

    elif shdr_type == "swat":
        water_shader = meta.swat_attrs.water_shader
        min_prio.val = heuristic_deprotect(
            get_tag_id(water_shader.base_map),
            name="%s_swat_base" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(water_shader.reflection_map),
            name="%s_swat_reflection" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(water_shader.ripple_maps),
            name="%s_swat_ripples" % name, **kw)

    elif shdr_type == "sgla":
        sgla_attrs = meta.sgla_attrs
        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.background_tint_properties.map),
            name="%s_sgla_background_tint" % name, **kw)

        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.reflection_properties.map),
            name="%s_sgla_reflection" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.reflection_properties.bump_map),
            name="%s_sgla_bump" % name, **kw)

        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.diffuse_properties.map),
            name="%s_sgla_diffuse" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.diffuse_properties.detail_map),
            name="%s_sgla_diffuse_detail" % name, **kw)

        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.specular_properties.map),
            name="%s_sgla_specular" % name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(sgla_attrs.specular_properties.detail_map),
            name="%s_sgla_specular_detail" % name, **kw)

    elif shdr_type == "smet":
        smet_attrs = meta.smet_attrs
        smet_srcs = smet_attrs.external_function_sources
        meter_name = ""
        for b in (smet_srcs.value, smet_srcs.flash_extension):
            func_name = kw.get("func_%s_name" % b.data, "")
            if func_name:
                meter_name = func_name

        if not meter_name:
            meter_name = name if "meter" in name else name + " meter"

        min_prio.val = heuristic_deprotect(get_tag_id(smet_attrs.meter_shader.map),
                         name="%s_smet" % name, **kw)

    elif shdr_type == "spla":
        spla_attrs = meta.spla_attrs
        plasma_name = ""
        func_name = kw.get(
            "func_%s_name" % spla_attrs.intensity.source.data, "")
        if func_name:
            plasma_name = func_name

        min_prio.val = heuristic_deprotect(
            get_tag_id(spla_attrs.primary_noise_map.noise_map),
            name="%s_spla_noise" % plasma_name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(spla_attrs.primary_noise_map.noise_map),
            name="%s_spla_noise_sec" % plasma_name, **kw)


def rename_item_attrs(meta, tag_id, halo_map, tag_path_handler,
                      root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler,
              return_on_equal_min_priority=True)

    item_attrs = meta.item_attrs
    eqip_attrs = getattr(meta, "eqip_attrs", None)
    weap_attrs = getattr(meta, "weap_attrs", None)

    items_dir = '\\'.join(sub_dir.split('\\')[: -2])
    if items_dir: items_dir += "\\"
    min_prio.val = heuristic_deprotect(get_tag_id(item_attrs.material_effects),
                     sub_dir=items_dir, name="material effects", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(item_attrs.collision_sound),
                     sub_dir=sub_dir + "sfx\\",
                     name="collision sound", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(item_attrs.detonating_effect),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="item detonating", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(item_attrs.detonation_effect),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="item detonation", **kw)

    if eqip_attrs:
        min_prio.val = heuristic_deprotect(get_tag_id(eqip_attrs.pickup_sound),
                         sub_dir=sub_dir + sound_dir,
                         name="pickup sound", **kw)

    if not weap_attrs:
        return

    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.ready_effect),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="weap ready", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.heat.overheated),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="weap overheated", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.heat.detonation),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="weap detonation", **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.melee.player_damage),
                     sub_dir=sub_dir, name="melee", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.melee.player_response),
                     sub_dir=sub_dir, name="melee response", **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.aiming.actor_firing_parameters),
                     sub_dir=sub_dir, name="firing parameters", **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.light.power_on_effect),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="light power on", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(weap_attrs.light.power_off_effect),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="light power off", **kw)

    interface = weap_attrs.interface
    min_prio.val = heuristic_deprotect(get_tag_id(interface.first_person_model),
                     sub_dir=sub_dir + weap_fp_dir, name="fp", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(interface.first_person_animations),
                     sub_dir=sub_dir + weap_fp_dir, name="fp", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(interface.hud_interface),
                     sub_dir=sub_dir, name=name, **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(interface.pickup_sound), name="weap pickup",
                     sub_dir=sub_dir + "sfx\\", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(interface.zoom_in_sound), name="zoom in",
                     sub_dir=sub_dir + "sfx\\", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(interface.zoom_out_sound), name="zoom out",
                     sub_dir=sub_dir + "sfx\\", **kw)

    i = 0
    for mag in weap_attrs.magazines.STEPTREE:
        mag_str = ""
        if len(weap_attrs.magazines.STEPTREE) > 1:
            mag_str = "secondary " if i else "primary "

        min_prio.val = heuristic_deprotect(
            get_tag_id(mag.reloading_effect), name="%sreloading" % mag_str,
            sub_dir=sub_dir + obje_effects_dir, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(mag.chambering_effect), name="%schambering" % mag_str,
            sub_dir=sub_dir + obje_effects_dir, **kw)

        j = 0
        for mag_item in mag.magazine_items.STEPTREE:
            mag_item_name = mag_str
            if len(mag.magazine_items.STEPTREE) > 1:
                mag_item_name += "secondary " if j else "primary "

            mag_item_name = "%s%s ammo" % (mag_item_name, name)
            min_prio.val = heuristic_deprotect(
                get_tag_id(mag_item.equipment), name=mag_item_name,
                sub_dir=powerups_dir + mag_item_name + "\\", **kw)
            j += 1

        i += 1

    i = 0
    kw["override"] = True
    for trig in weap_attrs.triggers.STEPTREE:
        trig_str = ""
        if len(weap_attrs.triggers.STEPTREE) > 1:
            trig_str = "secondary " if i else "primary "

        min_prio.val = heuristic_deprotect(
            get_tag_id(trig.charging.charging_effect),
            name="%scharging" % trig_str,
            sub_dir=sub_dir + obje_effects_dir, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(trig.projectile.projectile), name="projectile",
            sub_dir=sub_dir + "%sprojectile\\" % trig_str, **kw)

        for b in trig.firing_effects.STEPTREE:
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.firing_effect), name=trig_str + "fire",
                sub_dir=sub_dir + obje_effects_dir, **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.misfire_effect), name=trig_str + "misfire",
                sub_dir=sub_dir + obje_effects_dir, **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.empty_effect), name=trig_str + "empty",
                sub_dir=sub_dir + obje_effects_dir, **kw)

            min_prio.val = heuristic_deprotect(
                get_tag_id(b.firing_damage), name=trig_str + "fire response",
                sub_dir=sub_dir + "firing effects\\", **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.misfire_damage), name=trig_str + "misfire response",
                sub_dir=sub_dir + "firing effects\\", **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(b.empty_damage), name=trig_str + "empty response",
                sub_dir=sub_dir + "firing effects\\", **kw)

        i += 1


def rename_unit_attrs(meta, tag_id, halo_map, tag_path_handler,
                      root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler,
              return_on_equal_min_priority=True)

    unit_attrs = meta.unit_attrs
    bipd_attrs = getattr(meta, "bipd_attrs", None)
    vehi_attrs = getattr(meta, "vehi_attrs", None)

    weap_array = unit_attrs.weapons.STEPTREE
    weap_kwargs = dict(kw)
    weap_kwargs['priority'] = (VEHICLE_WEAP_PRIORITY if
                               kw.get("priority", 0) < VEHICLE_WEAP_PRIORITY
                               else kw.get("priority", 0))

    min_prio.val = heuristic_deprotect(get_tag_id(unit_attrs.integrated_light_toggle),
                     sub_dir=sub_dir + obje_effects_dir,
                     name="integrated light toggle", **kw)

    parent_dir = '\\'.join(sub_dir.split('\\')[: -2])
    if parent_dir: parent_dir += "\\"

    min_prio.val = heuristic_deprotect(get_tag_id(unit_attrs.spawned_actor), sub_dir=parent_dir,
                     name=(name + " spawned actor").strip(), **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(unit_attrs.melee_damage),
                     sub_dir=sub_dir, name="melee impact", **kw)

    unit_ext_array = getattr(getattr(unit_attrs, "unit_extensions", ()), "STEPTREE", ())
    trak_array = unit_attrs.camera_tracks.STEPTREE
    unhi_array = unit_attrs.new_hud_interfaces.STEPTREE
    udlg_array = unit_attrs.dialogue_variants.STEPTREE
    for i in range(len(trak_array)):
        min_prio.val = heuristic_deprotect(
            get_tag_id(trak_array[i].track), sub_dir=sub_dir,
            name={0:"loose", 1:"tight"}.get(i, "unknown"), **kw)

    for i in range(len(unhi_array)):
        min_prio.val = heuristic_deprotect(
            get_tag_id(unhi_array[i].unit_hud_interface), sub_dir=sub_dir,
            name={0:"sp", 1:"mp"}.get(i, "unknown"), **kw)

    for i in range(len(udlg_array)):
        min_prio.val = heuristic_deprotect(
            get_tag_id(udlg_array[i].dialogue),
            sub_dir=sub_dir, name=name + " dialogue", **kw)

    # there should only ever be 1 unit_ext and 1 mounted_state, so iterating
    # over them should really just collapse to a single iteration.
    for unit_ext in unit_ext_array:
      for mounted_state in unit_ext.mounted_states.STEPTREE:
        i = 0
        for b in mounted_state.camera_tracks.STEPTREE:
            min_prio.val = heuristic_deprotect(get_tag_id(b.track), sub_dir=sub_dir,
                             name={0:"mounted loose",
                                   1:"mounted tight"}.get(i, "unknown"), **kw)
            i += 1

        for b in mounted_state.keyframe_actions.STEPTREE:
            rename_keyframe_action(
                b, name, sub_dir=sub_dir + "mounted effects\\", **kw)

    trak_kwargs = dict(kw)
    trak_kwargs["priority"] = (DEFAULT_PRIORITY if
                               kw.get("priority", 0) < DEFAULT_PRIORITY
                               else kw.get("priority", 0))
    for seat in unit_attrs.seats.STEPTREE:
        seat_name = tag_path_handler.get_icon_string(
            seat.hud_text_message_index)
        if not seat_name:
            seat_name = sanitize_name(seat.label)
        if seat_name:
            seat_name += " "

        seat_ext_array = getattr(getattr(seat, "seat_extensions", ()), "STEPTREE", ())
        trak_array = seat.camera_tracks.STEPTREE
        unhi_array = seat.new_hud_interfaces.STEPTREE
        for i in range(len(trak_array)):
            min_prio.val = heuristic_deprotect(
                get_tag_id(trak_array[i].track), sub_dir=sub_dir,
                name=seat_name + {0:"loose", 1:"tight"}.get(i, "unknown"),
                **trak_kwargs)

        for i in range(len(unhi_array)):
            min_prio.val = heuristic_deprotect(
                get_tag_id(unhi_array[i].unit_hud_interface), sub_dir=sub_dir,
                name=seat_name + {0:"sp", 1:"mp"}.get(i, "unknown"), **kw)

        boarding_dir = sub_dir + "boarding\\"
        for seat_ext in seat_ext_array:
            for seat_boarding in seat_ext.seat_boarding.STEPTREE:
                for b in seat_boarding.seat_keyframe_actions.STEPTREE:
                    rename_keyframe_action(
                        b, seat_name, sub_dir=boarding_dir + effects_dir, **kw)

            for b in seat_ext.seat_damage.STEPTREE:
                min_prio.val = heuristic_deprotect(get_tag_id(b.melee_damage.damage_effect),
                                 sub_dir=boarding_dir,
                                 name=seat_name + " melee damage", **kw)
                min_prio.val = heuristic_deprotect(get_tag_id(b.region_targeting.damage_effect),
                                 sub_dir=boarding_dir,
                                 name=seat_name + " region damage", **kw)

        min_prio.val = heuristic_deprotect(get_tag_id(seat.built_in_gunner),
                         sub_dir=sub_dir, name="built in gunner", **kw)


    if bipd_attrs:
        min_prio.val = heuristic_deprotect(get_tag_id(bipd_attrs.movement.footsteps),
                         sub_dir=sub_dir, name="footsteps", **kw)


    if vehi_attrs:
        min_prio.val = heuristic_deprotect(get_tag_id(vehi_attrs.suspension_sound),
                         sub_dir=sub_dir, name="suspension sound", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(vehi_attrs.crash_sound),
                         sub_dir=sub_dir, name="crash sound", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(vehi_attrs.effect),
                         sub_dir=sub_dir, name="unknown effect", **kw)

        vehi_dir = '\\'.join(sub_dir.split('\\')[: -2])
        if vehi_dir: vehi_dir += "\\"
        min_prio.val = heuristic_deprotect(get_tag_id(vehi_attrs.material_effect),
                         sub_dir=vehi_dir, name="material effects", **kw)


    for i in range(len(weap_array)):
        gun_id = get_tag_id(weap_array[i].weapon)
        gun_meta = halo_map.get_meta(gun_id)
        gun_obje_attrs = getattr(gun_meta, "obje_attrs", None)
        if gun_obje_attrs is None:
            continue

        gun_mod2_id = get_tag_id(gun_obje_attrs.model)
        if gun_mod2_id is not None:
            continue

        gun_name = name + " gun"
        if len(weap_array) > 1:
            gun_name += " %s" % i

        min_prio.val = heuristic_deprotect(gun_id, name=gun_name,
                         sub_dir=sub_dir + gun_name + "\\", **weap_kwargs)


def rename_devi_attrs(meta, tag_id, halo_map, tag_path_handler,
                      root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
              sub_dir=sub_dir + obje_effects_dir,
              tag_path_handler=tag_path_handler)

    devi_attrs = meta.devi_attrs
    ctrl_attrs = getattr(meta, "ctrl_attrs", None)

    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.open), name="open", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.close), name="close", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.opened), name="opened", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.closed), name="closed", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.depowered), name="depowered", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.repowered), name="repowered", **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(devi_attrs.delay_effect), name="delay", **kw)

    if ctrl_attrs:
        min_prio.val = heuristic_deprotect(get_tag_id(ctrl_attrs.on), name="on", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(ctrl_attrs.off), name="off", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(ctrl_attrs.deny), name="deny", **kw)


def rename_actv(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name:
        name = "protected_%s" % tag_id
    if not sub_dir:
        sub_dir = characters_dir + name + "\\"

    kw.setdefault('priority', DEFAULT_PRIORITY)
    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    orig_priority = kw["priority"]

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    unit_id = get_tag_id(meta.unit)
    major_id = get_tag_id(meta.major_variant)
    for sub_id, name_modifier in ((unit_id, " unit"), (major_id, " major")):
        if tag_path_handler.get_priority(sub_id) > kw['priority']:
            sub_name = tag_path_handler.get_basename(sub_id)
            sub_dir = tag_path_handler.get_sub_dir(sub_id, root_dir)
            new_priority = tag_path_handler.get_priority(sub_id)
            # don't want to override infinite priority
            kw.update(override=(new_priority < INF), priority=new_priority)

            if sub_id == unit_id and sub_name.endswith(name_modifier):
                sub_name = "".join(sub_name.split(name_modifier)[:-1])

            if not sub_name.startswith("protected"):
                name = sub_name.lower()

            break

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.unit), sub_dir=sub_dir, name=name, **kw)

    kw["override"] = True
    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.actor_definition), sub_dir=sub_dir,
        name=name + " actor", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.major_variant), sub_dir=sub_dir,
        name=name + " major", **kw)

    # don't want to tie any items to an actor_variant with infinite priority
    if kw.get("priority", 0) > UNIT_WEAPON_PRIORITY:
        kw["priority"] = UNIT_WEAPON_PRIORITY

    min_prio.val = heuristic_deprotect(get_tag_id(meta.ranged_combat.weapon), sub_dir=sub_dir,
                     name=name + " weapon", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.items.equipment), sub_dir=sub_dir,
                     name=name + " drop", **kw)


def rename_flag(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return
    elif not name:
        name = 'flag'

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    shader_name = name
    if "flag" not in shader_name.lower():
        shader_name += "flag"

    shdr_dir = '\\'.join(sub_dir.split('\\')[: -2])
    if shdr_dir: shdr_dir += "\\"
    shdr_dir += shaders_dir
    min_prio.val = heuristic_deprotect(get_tag_id(meta.red_flag_shader), sub_dir=shdr_dir,
                     name=shader_name + "_red", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.blue_flag_shader), sub_dir=shdr_dir,
                     name=shader_name + "_blue", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.physics), sub_dir=sub_dir,
                     name=name, **kw)


def rename_mode(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    if not name or name.startswith("protected"):
        name = tag_path_handler.get_basename(tag_id)

    model_name = get_model_name(meta=meta)
    if (not name or name.startswith("protected")) and model_name:
        name = model_name
        kw.setdefault('priority',
            MEDIUM_HIGH_PRIORITY if kw.get("prioritize_model_names") else 
            MEDIUM_PRIORITY
            )

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))

    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir,
              sub_dir=sub_dir + shaders_dir,
              tag_path_handler=tag_path_handler)

    shader_names = {}
    for i in range(len(meta.regions.STEPTREE)):
        region = meta.regions.STEPTREE[i]
        geoms = []

        region_name = region.name.lower().strip("_ ").replace("unnamed", "")
        if region_name: region_name += " "

        for j in range(len(region.permutations.STEPTREE)):
            perm = region.permutations.STEPTREE[j]
            shader_name = sanitize_model_or_sound_name(
                region_name + "_" + perm.name
                ) or model_name

            for lod in ("superhigh", "high", "medium", "low", "superlow"):
                geom_index = getattr(perm, lod + "_geometry_block")

                if geom_index not in range(len(meta.geometries.STEPTREE)):
                    continue

                parts = meta.geometries.STEPTREE[geom_index].parts.STEPTREE
                for part_i in range(len(parts)):
                    final_shader_name = shader_name
                    if len(parts) > 1:
                        final_shader_name += "_part%s" % part_i
                    if lod != "superhigh":
                        final_shader_name += "_" + lod
                    shader_names.setdefault(parts[part_i].shader_index,
                                            final_shader_name)

    for i in range(len(meta.shaders.STEPTREE)):
        min_prio.val = heuristic_deprotect(get_tag_id(meta.shaders.STEPTREE[i].shader),
                         name=shader_names.get(i, ""), **kw)


def rename_coll(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  sub_dir=sub_dir + obje_effects_dir,
                  tag_path_handler=tag_path_handler)

    body, shield = meta.body, meta.shield
    min_prio.val = heuristic_deprotect(get_tag_id(body.localized_damage_effect),
                     name=name + " localized damage", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(body.area_damage_effect),
                     name=name + " area damage", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(body.body_damaged_effect),
                     name=name + " body damaged", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(body.body_depleted_effect),
                     name=name + " body depleted", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(body.body_destroyed_effect),
                     name=name + " body destroyed", **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(shield.shield_damaged_effect),
                     name=name + " shield damaged", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(shield.shield_depleted_effect),
                     name=name + " shield depleted", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(shield.shield_recharging_effect),
                     name=name + " shield recharging", **kw)

    i = 0
    for region in meta.regions.STEPTREE:
        region_name = sanitize_name_piece(region.name, "region %s" % i)
        min_prio.val = heuristic_deprotect(
            get_tag_id(region.destroyed_effect),
            name=("%s %s destroyed" % (name, region_name)).strip(), **kw)
        i += 1


def rename_rain(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = weather_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    weather_bitmaps_dir = sub_dir + bitmaps_dir

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)

    i = 0
    for b in meta.particle_types.STEPTREE:
        type_name = sanitize_name_piece(b.name, "particle %s" % i)
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.physics), sub_dir=effect_physics_dir,
            name=name + type_name, **kw)

        min_prio.val = heuristic_deprotect(
            get_tag_id(b.shader.sprite_bitmap), sub_dir=weather_bitmaps_dir,
            name=name + (type_name + " sprites").strip(), **kw)

        min_prio.val = heuristic_deprotect(
            get_tag_id(b.secondary_bitmap.bitmap), sub_dir=weather_bitmaps_dir,
            name=name + (type_name + " sec map").strip(), **kw)
        i += 1


def rename_fog_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = weather_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.screen_layers.fog_map), sub_dir=sub_dir + bitmaps_dir,
        name=(name + " fog map").strip(), **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.background_sound), sub_dir=sub_dir,
        name=(name + " fog background sound").strip(), **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.sound_environment), sub_dir=sub_dir,
        name=(name + " fog sound environment").strip(), **kw)


def rename_foot(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    for i in range(len(meta.effects.STEPTREE)):
        type_dir = material_effect_types[i] + "\\"
        mat_effects_dir = sub_dir + name + "\\" + effects_dir + type_dir
        mat_sounds_dir = sub_dir + name + "\\" + sounds_dir + type_dir
        materials = meta.effects.STEPTREE[i].materials.STEPTREE

        for j in range(len(materials)):
            min_prio.val = heuristic_deprotect(get_tag_id(materials[j].effect),
                             sub_dir=mat_effects_dir,
                             name=materials_list[j], **kw)
            min_prio.val = heuristic_deprotect(get_tag_id(materials[j].sound),
                             sub_dir=mat_sounds_dir,
                             name=materials_list[j], **kw)


def rename_antr(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return
    elif not name:
        name = 'animations'

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault("priority", DEFAULT_PRIORITY)

    sfx_names = {}
    for i in range(len(meta.animations.STEPTREE)):
        anim = meta.animations.STEPTREE[i]
        sfx_names.setdefault(anim.sound, anim.name.replace(".", " ").strip())

    anim_sfx_dir = sub_dir + "anim_sfx\\"
    for i in range(len(meta.sound_references.STEPTREE)):
        min_prio.val = heuristic_deprotect(
            get_tag_id(meta.sound_references.STEPTREE[i].sound),
            name=sfx_names.get(i, name), sub_dir=anim_sfx_dir, **kw)

    if hasattr(meta, "stock_animation"):
        min_prio.val = heuristic_deprotect(
            get_tag_id(meta.stock_animation),
            name=name + " base", sub_dir=sub_dir, **kw)


def rename_deca(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler,
              return_on_equal_min_priority=True)

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return
    elif not name:
        name = 'decal %s' % tag_id

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.shader.shader_map), name=name + " bitmaps",
                     sub_dir=sub_dir + bitmaps_dir, **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.next_decal_in_chain), name=name + " next",
                     sub_dir=sub_dir, **kw)


def rename_ant_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return
    elif not name:
        name = 'antenna'

        if 'antenna' not in meta.attachment_marker_name:
            name += meta.attachment_marker_name

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    bitm_dir = '\\'.join(sub_dir.split('\\')[: -2])
    if bitm_dir: bitm_dir += "\\"
    bitm_dir += bitmaps_dir
    min_prio.val = heuristic_deprotect(get_tag_id(meta.bitmaps), sub_dir=bitm_dir,
                     name=name, **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.physics), sub_dir=sub_dir,
                     name=name, **kw)


def rename_dobc(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    dobc_type_names = set()
    for b in meta.detail_object_types.STEPTREE:
        dobc_name = b.name.lower().replace("_", " ").strip()
        if dobc_name:
            dobc_type_names.add(dobc_name)

    dobc_name = join_names(sorted(dobc_type_names), 96)
    if (not name or "protected" in name) and dobc_name: name = dobc_name

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.sprite_plate), halo_map, tag_path_handler,
        root_dir, sub_dir + bitmaps_dir, dobc_name, **kw)


def rename_udlg(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))
    name = tag_path_handler.get_basename(tag_id)
    sub_dir = snd_dialog_dir + name + "\\"

    for struct in (meta.idle, meta.involuntary, meta.hurting_people,
                   meta.being_hurt, meta.killing_people, meta.actions,
                   meta.player_kill_responses, meta.friends_dying,
                   meta.shouting, meta.group_communication, meta.exclamations,
                   meta.post_combat_actions, meta.post_combat_chatter):
        snd_dir = sub_dir + "%s\\" % struct.NAME
        for dep in struct:
            min_prio.val = heuristic_deprotect(get_tag_id(dep), halo_map, tag_path_handler,
                             root_dir, snd_dir, dep.NAME, **kw)


def rename_DeLa(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return
    if not name:
        name = kw.get("dela_name", "").replace("_", " ").strip()
        if not name:
            name = sanitize_name(meta.name)
    if not sub_dir:
        sub_dir = ui_shell_dir

    kw.pop("dela_name", None)
    seen = kw.get("seen", set())

    if not name:
        name = "protected_%s" % tag_id

    kw["priority"] = (MEDIUM_HIGH_PRIORITY if
                      kw.get("priority", 0) < MEDIUM_HIGH_PRIORITY
                      else kw.get("priority", 0))
    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    for b in meta.event_handlers.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.sound_effect), sub_dir=sub_dir + "sfx\\", **kw)

        if (tag_path_handler.get_priority(get_tag_id(b.widget_tag)) >=
            kw["priority"] and tag_id in seen):
            continue
        min_prio.val = heuristic_deprotect(get_tag_id(b.widget_tag), sub_dir=sub_dir, **kw)


    kw.update(sub_dir=sub_dir + bitmaps_dir)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.background_bitmap),
                     name=name + " bg", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.spinner_list.list_header_bitmap),
                     name=name + " header", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.spinner_list.list_footer_bitmap),
                     name=name + " footer", **kw)

    kw.update(sub_dir=sub_dir + name + "\\")
    min_prio.val = heuristic_deprotect(get_tag_id(meta.text_box.text_label_unicode_strings_list),
                     name="text labels", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.text_box.text_font),
                     name="text font", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.column_list.extended_description_widget),
                     name="ext desc", **kw)

    if kw.get("shallow_ui_widget_nesting"):
        kw.update(sub_dir=sub_dir)

    for b in meta.conditional_widgets.STEPTREE:
        if (tag_path_handler.get_priority(get_tag_id(b.widget_tag)) >=
            kw["priority"] and tag_id in seen):
            continue
        min_prio.val = heuristic_deprotect(get_tag_id(b.widget_tag),
                         dela_name=sanitize_name(b.name), **kw)

    for b in meta.child_widgets.STEPTREE:
        if (tag_path_handler.get_priority(get_tag_id(b.widget_tag)) >=
            kw["priority"] and tag_id in seen):
            continue
        min_prio.val = heuristic_deprotect(get_tag_id(b.widget_tag),
                         dela_name=sanitize_name(b.name), **kw)


def rename_lsnd(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir:
        sub_dir = snd_music_dir

    meta = halo_map.get_meta(tag_id, recache=True)
    if meta is None:
        return

    if not name or name.startswith("protected"):
        name = get_sound_looping_name(meta, halo_map, "protected_%s" % tag_id)

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.continuous_damage_effect),
        name=name + " continuous damage", sub_dir=sub_dir, **kw)

    i = 0
    tracks_dir = sub_dir + name + " tracks & details\\"
    for b in meta.tracks.STEPTREE:
        for tag_ref, sub_name in ((
            [b.start,           "track %s start"    % i],
            [b.loop,            "track %s loop"     % i],
            [b.end,             "track %s end"      % i],
            [b.alternate_loop,  "track %s alt loop" % i],
            [b.alternate_end,   "track %s alt end"  % i],
            )):
            min_prio.val = heuristic_deprotect(
                get_tag_id(tag_ref), name=sub_name,
                sub_dir=tracks_dir, **kw)

        i += 1

    i = 0
    for b in meta.detail_sounds.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.sound), name="detail sound %s" % i,
            sub_dir=tracks_dir, **kw)
        i += 1


def rename_snd_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id, ignore_rawdata=True)
    non_rsrc_meta = halo_map.get_meta(tag_id, False, True, ignore_rawdata=True)
    if meta is None:
        return
    sub_dir2, name2 = get_sound_sub_dir_and_name(meta, sub_dir, name)
    if not sub_dir:
        sub_dir = sub_dir2
    if (not name or name.startswith("protected")) and name2:
        name = name2

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority'),
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(non_rsrc_meta.promotion_sound), halo_map,
                     tag_path_handler, root_dir, sub_dir,
                     name + " promo", **kw)


def rename_vcky(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = ui_dir
    if not name: name = "virtual kbd english"

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.display_font),
        sub_dir=sub_dir, name="virtual kbd font", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.special_key_labels_string_list),
        sub_dir=sub_dir, name="virtual kbd key labels", **kw)

    kw.update(sub_dir=sub_dir + "virtual kbd bitmaps\\")
    min_prio.val = heuristic_deprotect(get_tag_id(meta.background_bitmap),
                     name="background", **kw)
    for b in meta.virtual_keys.STEPTREE:
        key_name = b.keyboard_key.enum_name
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.unselected_background_bitmap),
            name=key_name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.selected_background_bitmap),
            name="highlight " + key_name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.active_background_bitmap),
            name="select " + key_name, **kw)
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.sticky_background_bitmap),
            name="engaged " + key_name, **kw)


def rename_soul(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = ui_shell_dir
    if not name: name = "protected_%s" % tag_id

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)
    for b in meta.ui_widget_definitions.STEPTREE:
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.ui_widget_definition), sub_dir=sub_dir, **kw)


def rename_tagc(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw['priority'] = LOW_PRIORITY  # tag collections contain so many various
    #                                things that it's not smart to expect
    #                                their contents should share the tag
    #                                collection's priority or directory
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(sub_dir=sub_dir + name + "\\")
    for b in meta.tag_references.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.tag), **kw)


def rename_trak(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + (sub_dir if sub_dir else camera_dir) + name,
        kw.get('priority', LOW_PRIORITY), kw.get("override"),
        kw.get("do_printout"))


def rename_snde(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + (sub_dir if sub_dir else snd_sound_env_dir) + name,
        kw.get('priority', LOW_PRIORITY), kw.get("override"),
        kw.get("do_printout"))


def rename_devc(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir:
        sub_dir = ui_devc_def_dir
        kw.setdefault("priority", MEDIUM_PRIORITY)
    if not name:
        name = tag_path_handler.get_basename(tag_id)

    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw.get('priority', DEFAULT_PRIORITY),
        kw.get("override"), kw.get("do_printout"))


def rename_ligh(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_lights_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.lens_flare),
                     sub_dir=sub_dir, name=name + " lens flare", **kw)

    sub_dir = sub_dir + bitmaps_dir
    min_prio.val = heuristic_deprotect(get_tag_id(meta.gel_map.primary_cube_map),
                     sub_dir=sub_dir, name=name + " gel glow pri", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.gel_map.secondary_cube_map),
                     sub_dir=sub_dir, name=name + " gel glow sec", **kw)


def rename_glw_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_lights_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.texture), name=name + " glow sprite",
                     sub_dir=sub_dir + bitmaps_dir, **kw)


def rename_lens(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_lens_flares_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.bitmaps.bitmap),
                     name=name + " bitmaps",
                     sub_dir=sub_dir + bitmaps_dir, **kw)


def rename_mgs2(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_lens_flares_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.map), name=name + " light vol map",
                     sub_dir=sub_dir + bitmaps_dir, **kw)


def rename_elec(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_lens_flares_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.bitmap), name=name + " elec map",
                     sub_dir=sub_dir + bitmaps_dir, **kw)


def rename_part(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_particles_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.physics),
                     sub_dir=sub_dir + effects_dir, name=name, **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.impact_effect),
                     sub_dir=sub_dir + effects_dir,
                     name=name + " impact effect", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.collision_effect),
                     sub_dir=sub_dir + effects_dir,
                     name=name + " collision", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.death_effect),
                     sub_dir=sub_dir + effects_dir,
                     name=name + " death", **kw)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.bitmap),
                     sub_dir=sub_dir + bitmaps_dir,
                     name=name + " sprite", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.secondary_map.bitmap),
                     sub_dir=sub_dir + bitmaps_dir,
                     name=name + " sprite sec", **kw)


def rename_pctl(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_contrails_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.point_physics), sub_dir=sub_dir,
                     name=name + " default physics", **kw)
    i = 0
    for b in meta.particle_types.STEPTREE:
        t_name = name + " " + sanitize_name_piece(b.name, "type %s" % i)

        j = 0
        for s in b.particle_states.STEPTREE:
            s_name = t_name + " " + sanitize_name_piece(s.name, "state %s" % j)

            min_prio.val = heuristic_deprotect(get_tag_id(s.physics),
                             sub_dir=sub_dir + effects_dir,
                             name=s_name, **kw)
            min_prio.val = heuristic_deprotect(get_tag_id(s.bitmaps),
                             sub_dir=sub_dir + bitmaps_dir,
                             name=s_name + " bitmaps", **kw)
            min_prio.val = heuristic_deprotect(get_tag_id(s.secondary_map.bitmap),
                             sub_dir=sub_dir + bitmaps_dir,
                             name=s_name + " bitmaps sec", **kw)
            j += 1
        i += 1


def rename_cont(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effect_contrails_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.rendering.bitmap),
                     sub_dir=sub_dir + bitmaps_dir,
                     name=name + " sprite", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.secondary_map.bitmap),
                     sub_dir=sub_dir + bitmaps_dir,
                     name=name + " sprite sec", **kw)

    for b in meta.point_states.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.physics), sub_dir=sub_dir,
                         name=name, **kw)


def rename_jpt_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effects_dir + "damage\\"

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.sound), sub_dir=sub_dir,
                     name=name + " sfx", **kw)


def rename_effe(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = effects_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, sub_dir=sub_dir + name + " events\\",
              root_dir=root_dir, tag_path_handler=tag_path_handler,
              return_on_equal_min_priority=True)

    i = 0
    event_name = ""
    for event in meta.events.STEPTREE:
        if len(meta.events.STEPTREE) > 1:
            event_name = "event %s " % i

        j = 0
        for b in event.parts.STEPTREE:
            min_prio.val = heuristic_deprotect(get_tag_id(b.type),
                             name=event_name + "part %s" % j, **kw)
            j += 1

        j = 0
        for b in event.particles.STEPTREE:
            min_prio.val = heuristic_deprotect(get_tag_id(b.particle_type),
                             name=event_name + "particle %s" % j, **kw)
            j += 1

        i += 1


def rename_multitex_overlay(block, name, overlay_name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if block is None:
        return

    if overlay_name:
        name += " " + overlay_name
    else:
        name += " " + block.NAME

    min_prio.val = heuristic_deprotect(get_tag_id(block.primary_map), name=name + " pri", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(block.secondary_map), name=name + " sec", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(block.tertiary_map), name=name + " ter", **kw)


def rename_hud_background(block, name, background_name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if block is None:
        return

    if background_name:
        name += " " + background_name
    else:
        name += " " + block.NAME.replace("background", "bg")

    min_prio.val = heuristic_deprotect(get_tag_id(block.interface_bitmap), name=name, **kw)
    for b in block.multitex_overlays.STEPTREE:
        rename_multitex_overlay(b, name, "static element", **kw)


def rename_grhi(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = ui_hud_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = "hud " + tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, sub_dir=sub_dir + bitmaps_dir)

    rename_hud_background(meta.grenade_hud_background, name, **kw)
    rename_hud_background(meta.total_grenades.background, name, **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.total_grenades.overlay_bitmap),
        name=name + " grenades overlay", **kw)

    kw.update(sub_dir=sub_dir + sounds_dir + name + "\\")
    for b in meta.warning_sounds.STEPTREE:
        snd_name = ""
        for flag_name in sorted(b.latched_to.NAME_MAP):
            if b.latched_to[flag_name]:
                snd_name += flag_name + " & "
        if not snd_name:
            snd_name = "unused"
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.sound), name=snd_name.strip(" &"), **kw)


def rename_unhi(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = ui_hud_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = "hud " + tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, sub_dir=sub_dir + bitmaps_dir)

    rename_hud_background(meta.unit_hud_background, name, **kw)
    rename_hud_background(meta.shield_panel_background, name, **kw)
    rename_hud_background(meta.health_panel_background, name, **kw)
    rename_hud_background(meta.motion_sensor_background, name, **kw)
    rename_hud_background(meta.motion_sensor_foreground, name, **kw)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.health_panel_meter.meter_bitmap),
        name=name + " health meter", **kw)
    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.shield_panel_meter.meter_bitmap),
        name=name + " shield meter", **kw)

    for b in meta.auxilary_overlays.STEPTREE:
        rename_hud_background(b.background, name, "flashlight overlay", **kw)

    for b in meta.auxilary_meters.STEPTREE:
        rename_hud_background(b.background, name, "flashlight meter bg", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.meter_bitmap),
                                        name=name + "flashlight meter", **kw)

    kw.update(sub_dir=sub_dir + sounds_dir + name + "\\")
    for b in meta.warning_sounds.STEPTREE:
        snd_name = ""
        for flag_name in sorted(b.latched_to.NAME_MAP):
            if b.latched_to[flag_name]:
                snd_name += flag_name + " & "
        if not snd_name:
            snd_name = "unused"
        min_prio.val = heuristic_deprotect(
            get_tag_id(b.sound), name=snd_name.strip(" &"), **kw)


def rename_wphi(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = ui_hud_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, )#sub_dir=sub_dir)

    min_prio.val = heuristic_deprotect(
        get_tag_id(meta.child_hud),
        name=name + ("" if name.endswith("child") else " child"), **kw)
    name = "hud " + name

    kw.update(sub_dir=sub_dir + bitmaps_dir)
    for b in meta.static_elements.STEPTREE:
        rename_hud_background(b, name, "static elements", **kw)

    for b in meta.meter_elements.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.meter_bitmap),
                                        name=name + " meter element", **kw)

    for b in meta.crosshairs.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.crosshair_bitmap),
                                        name=name + " crosshair", **kw)

    for b in meta.overlay_elements.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.overlay_bitmap),
                                        name=name + " overlay", **kw)

    for b in meta.screen_effect.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.mask.fullscreen_mask),
                                        name=name + " fullscreen mask", **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.mask.splitscreen_mask),
                                        name=name + " splitscreen mask", **kw)


def rename_mply(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "multiplayer_scenarios"
    if not sub_dir: sub_dir = ui_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
                  root_dir=root_dir, sub_dir=sub_dir + name + "\\")

    for b in meta.multiplayer_scenario_descriptions.STEPTREE:
        name = sanitize_name(b.scenario_tag_directory_path).split("\\")[-1]
        min_prio.val = heuristic_deprotect(get_tag_id(b.descriptive_bitmap), name=name, **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.displayed_map_name), name=name, **kw)


def rename_ngpr(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    meta_name = sanitize_name(meta.name)
    if not name: name = meta_name if meta_name else "protected_%s" % tag_id
    if not sub_dir: sub_dir = ui_shell_dir + "netgame_prefs\\"

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.pattern), sub_dir=sub_dir + bitmaps_dir,
                     name=name + " pattern", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.decal), sub_dir=sub_dir + bitmaps_dir,
                     name=name + " decal", **kw)


def rename_hud_(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "counter"
    if not sub_dir: sub_dir = ui_hud_dir

    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.digits_bitmap), sub_dir=sub_dir,
                     name=name + " digits", **kw)


def rename_yelo(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name:
        name = 'yelo'
    if not sub_dir:
        sub_dir = levels_dir + sanitize_name(
            halo_map.map_header.map_name) + "\\" + globals_dir

    kw.update(halo_map=halo_map, root_dir=root_dir,
              tag_path_handler=tag_path_handler)
    kw.setdefault('priority', INF)

    meta = halo_map.get_meta(tag_id, reextract=True)
    if meta is None:
        return

    # rename this project_yellow tag
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    override_kw = dict(kw)
    override_kw['priority'] = INF

    # rename the yelo globals
    min_prio.val = heuristic_deprotect(get_tag_id(meta.yelo_globals),
                     sub_dir=sub_dir, name="yelo globals", **override_kw)

    # rename the globals override
    min_prio.val = heuristic_deprotect(get_tag_id(meta.globals_override),
                     sub_dir=sub_dir, name="globals", **override_kw)

    # rename the explicit references
    min_prio.val = heuristic_deprotect(get_tag_id(meta.scenario_explicit_references),
                     sub_dir=sub_dir, name="scenario refs", **override_kw)

    # rename scripted ui widget references
    kw['priority'], i = 0.6, 0
    widgets_dir = ui_dir + "yelo widgets\\"
    for b in meta.scripted_ui_widgets.STEPTREE:
        widget_name = sanitize_name(b.name)
        if not widget_name:
            widget_name = "scripted ui widget %s" % i
        min_prio.val = heuristic_deprotect(get_tag_id(b.definition), sub_dir=widgets_dir,
                         name=widget_name, **kw)
        i += 1


def rename_gelo(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = levels_dir

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', INF)

    meta = halo_map.get_meta(tag_id, reextract=True)
    if meta is None:
        return
    elif not name:
        name = 'yelo globals'

    # rename this project_yellow_globals tag
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    # rename the explicit references
    min_prio.val = heuristic_deprotect(get_tag_id(meta.global_explicit_references),
                     name="global refs", **kw)

    # rename the chokin victim globals
    try:
        sub_id = get_tag_id(meta.chokin_victim_globals)
    except AttributeError:
        sub_id = None
    if sub_id is not None:
        min_prio.val = heuristic_deprotect(sub_id, sub_dir=sub_dir, name="yelo globals cv", **kw)

    # rename scripted ui widget references
    widgets_dir = ui_dir + "gelo widgets\\"
    for b in meta.scripted_ui_widgets.STEPTREE:
        widget_name = sanitize_name(b.name)
        if not widget_name:
            widget_name = "scripted ui widget %s" % i
        min_prio.val = heuristic_deprotect(get_tag_id(b.definition), sub_dir=widgets_dir,
                         name=widget_name, **kw)
        i += 1


def rename_gelc(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not sub_dir: sub_dir = levels_dir

    kw.update(halo_map=halo_map, root_dir=root_dir,
                  tag_path_handler=tag_path_handler)
    kw.setdefault('priority', INF)

    meta = halo_map.get_meta(tag_id, reextract=True)
    if meta is None:
        return
    elif not name:
        name = 'yelo globals cv'

    # rename this project_yellow_globals tag
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    # TODO: Finish this up if I feel the need to.
    # I'm not typing up the rest of this right now. Might be pointless anyway.


def rename_efpc(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    name = sanitize_name(halo_map.map_header.map_name) + " postprocess effects"
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, sub_dir=sub_dir + "postprocess\\")

    for b in meta.effects.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.effect), name=sanitize_name(b.name), **kw)


def rename_efpg(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    sub_dir = "postprocess\\"
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, sub_dir=sub_dir + name + " shaders\\")

    for b in meta.efpg_attrs.shaders.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.shader), **kw)


def rename_shpg(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = "postprocess\\"
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
                  root_dir=root_dir)

    min_prio.val = heuristic_deprotect(get_tag_id(meta.shpg_attrs.base_shader),
                     sub_dir=sub_dir, name=name + " base", **kw)

    kw.update(sub_dir=sub_dir + name + "\\")
    for b in meta.shpg_attrs.merged_values.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.bitmap),
                         name=sanitize_name(b.value_name), **kw)

    for b in meta.shpg_attrs.bitmaps.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.bitmap),
                         name=sanitize_name(b.value_name), **kw)


def rename_sppg(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if halo_map.get_meta(tag_id) is not None:
        min_prio.val = tag_path_handler.set_path_by_priority(
            tag_id, root_dir + "postprocess\\%s postprocess globals" %
            sanitize_name(halo_map.map_header.map_name),
            kw.get('priority', DEFAULT_PRIORITY),
            kw.get("override"), kw.get("do_printout"))


def rename_efpp(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    meta = halo_map.get_meta(tag_id)
    if meta is not None:
        min_prio.val = tag_path_handler.set_path_by_priority(
            tag_id, root_dir + "postprocess\\" + name,
            kw.get('priority', DEFAULT_PRIORITY),
            kw.get("override"), kw.get("do_printout"))


def rename_sily(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = ui_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, sub_dir=sub_dir + name + "\\")

    min_prio.val = heuristic_deprotect(get_tag_id(meta.parameter), name="parameter", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.title_text), name="title", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(meta.description_text),
                     name="description", **kw)

    kw.update(sub_dir=sub_dir + name + "\\string id pairs\\")
    i = 0
    for b in meta.string_references.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.string_id),
                         name=str(i), **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.label_string_id),
                         name="label %s" % i, **kw)
        min_prio.val = heuristic_deprotect(get_tag_id(b.description_string_id),
                         name="description %s" % i, **kw)
        i += 1


def rename_unic(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    if not sub_dir: sub_dir = ui_dir
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
                  root_dir=root_dir, sub_dir=sub_dir + name + " strings\\")

    for b in meta.string_references.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.string_id), name=name + " string id", **kw)


def rename_avtc(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    name = sanitize_name(halo_map.map_header.map_name) + " actor variant transforms"
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', VERY_HIGH_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + name, kw['priority'], True, kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir)

    sub_dir += "actor variant transforms\\"
    for b in meta.actor_variant_transforms.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.actor_variant), sub_dir=sub_dir, **kw)
        actv_name = tag_path_handler.get_basename(get_tag_id(b.actor_variant))
        actv_sub_dir = tag_path_handler.get_sub_dir(
            get_tag_id(b.actor_variant), root_dir) + "transforms\\"

        for transform in b.transforms.STEPTREE:
            stages = transform.transform_stages
            trans_name = sanitize_name(transform.transform_name)
            if not trans_name:
                trans_name = "unnamed"

            min_prio.val = heuristic_deprotect(
                get_tag_id(stages.transform_out), sub_dir=actv_sub_dir,
                name=trans_name + " transform out", **kw)
            min_prio.val = heuristic_deprotect(
                get_tag_id(stages.transform_in), sub_dir=actv_sub_dir,
                name=trans_name + " transform in", **kw)


def rename_keyframe_action(b, name, **kw):
    min_prio = kw.get("min_priority", MinPriority())
    min_prio.val = heuristic_deprotect(get_tag_id(b.damage_effect), name=name + " damage", **kw)
    min_prio.val = heuristic_deprotect(get_tag_id(b.effect), name=name + " effect", **kw)


def rename_atvi(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'], kw.get("override"),
        kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir)
    sub_dir += name + "\\"

    for target in meta.targets.STEPTREE:
        target_name = sanitize_name(target.target_name)
        if not target_name:
            target_name = "transform target"

        min_prio.val = heuristic_deprotect(get_tag_id(target.ai.actor_variant),
                         sub_dir=sub_dir, name=target_name, **kw)

        transform_name = sanitize_name(target.animation.transform_in_anim)
        if not transform_name:
            transform_name = "transform in"

        for b in target.animation.keyframe_actions.STEPTREE:
            rename_keyframe_action(b, transform_name,
                                   sub_dir=sub_dir + effects_dir, **kw)


def rename_atvo(tag_id, halo_map, tag_path_handler,
                root_dir="", sub_dir="", name="", **kw):
    min_prio = kw.get("min_priority", MinPriority())
    if not name: name = "protected_%s" % tag_id
    meta = halo_map.get_meta(tag_id)
    if meta is None:
        return

    kw.setdefault('priority', DEFAULT_PRIORITY)
    min_prio.val = tag_path_handler.set_path_by_priority(
        tag_id, root_dir + sub_dir + name, kw['priority'],
        kw.get("override"), kw.get("do_printout"))
    sub_dir = tag_path_handler.get_sub_dir(tag_id, root_dir)
    name = tag_path_handler.get_basename(tag_id)

    kw.update(halo_map=halo_map, tag_path_handler=tag_path_handler,
              root_dir=root_dir, sub_dir=sub_dir + name + "\\")

    for b in meta.transform_instigators.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.unit), name="instigator", **kw)

    for b in meta.attachments.attachments.STEPTREE:
        min_prio.val = heuristic_deprotect(get_tag_id(b.object),
                         name=sanitize_name(b.object_marker +
                                            " attachment").strip(), **kw)

    transform_name = sanitize_name(meta.animation.transform_out_anim)
    if not transform_name:
        transform_name = "transform out"

    kw["sub_dir"] += "keyframe actions\\"
    for b in meta.animation.keyframe_actions.STEPTREE:
        rename_keyframe_action(b, transform_name, **kw)


recursive_rename_functions = dict(
    scenario = rename_scnr,
    scenario_structure_bsp = rename_sbsp,
    detail_object_collection = rename_dobc,

    project_yellow = rename_yelo,
    project_yellow_globals = rename_gelo,
    project_yellow_globals_cv = rename_gelc,
    globals = rename_matg,
    hud_globals = rename_hudg,

    grenade_hud_interface = rename_grhi,
    weapon_hud_interface = rename_wphi,
    unit_hud_interface = rename_unhi,

    input_device_defaults = rename_devc,
    ui_widget_definition = rename_DeLa,
    virtual_keyboard = rename_vcky,

    hud_number = rename_hud_,
    multiplayer_scenario_description = rename_mply,
    preferences_network_game = rename_ngpr,

    tag_collection = rename_tagc,
    ui_widget_collection = rename_soul,

    camera_track = rename_trak,
    actor_variant = rename_actv,

    biped = rename_obje,
    vehicle = rename_obje,
    weapon = rename_obje,
    equipment = rename_obje,
    garbage = rename_obje,
    projectile = rename_obje,
    scenery = rename_obje,
    device_machine = rename_obje,
    device_control = rename_obje,
    device_light_fixture = rename_obje,
    placeholder = rename_obje,
    sound_scenery = rename_obje,

    sound = rename_snd_,
    sound_looping = rename_lsnd,
    dialogue = rename_udlg,
    sound_environment = rename_snde,

    effect = rename_effe,
    glow = rename_glw_,
    light = rename_ligh,
    light_volume = rename_mgs2,
    lightning = rename_elec,
    lens_flare = rename_lens,
    antenna = rename_ant_,
    flag = rename_flag,

    weather_particle_system = rename_rain,
    sky = rename_sky_,
    fog = rename_fog_,

    model_collision_geometry = rename_coll,

    material_effects = rename_foot,
    particle_system = rename_pctl,
    particle = rename_part,
    contrail = rename_cont,

    decal = rename_deca,
    damage_effect = rename_jpt_,

    gbxmodel = rename_mode,
    model = rename_mode,

    model_animations = rename_antr,
    model_animations_yelo = rename_antr,

    shader_transparent_chicago = rename_shdr,
    shader_transparent_chicago_extended = rename_shdr,
    shader_transparent_generic = rename_shdr,
    shader_environment = rename_shdr,
    shader_transparent_glass = rename_shdr,
    shader_transparent_meter = rename_shdr,
    shader_model = rename_shdr,
    shader_transparent_plasma = rename_shdr,
    shader_transparent_water = rename_shdr,

    effect_postprocess_collection = rename_efpc,
    effect_postprocess_generic = rename_efpg,
    effect_postprocess = rename_efpp,
    shader_postprocess_generic = rename_shpg,
    shader_postprocess_globals = rename_sppg,

    text_value_pair_definition = rename_sily,
    multilingual_unicode_string_list = rename_unic,

    actor_variant_transform_collection = rename_avtc,
    actor_variant_transform_in = rename_atvi,
    actor_variant_transform_out = rename_atvo,
    )
