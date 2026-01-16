import time
import os
import csv
import threading
import random
import pygame
import asyncio
import settings
from arena import build_sand_texture, build_wall_texture, draw_arena, draw_offer_lines, recalc_arena, spawn_gladiators, team_label
from entities import Projectile, TEAM_SYMBOL_NAMES
from agents import start_agents, stop_agents
from settings import build_state, draw_timer, draw_wood_panel, render_loading
from settings import (
    FPS,
    GLADIATOR_COUNT,
    KEY_ESCAPE,
    KEY_REFRESH,
    KEY_RESTART,
    KEY_START,
    LOADING_TEXT,
    REFRESHING_TEXT,
    RESTARTING_TEXT,
)


def run() -> None:
    pygame.init()
    info = pygame.display.Info()
    target_w = int(info.current_w * 0.8)
    target_h = int(target_w * (info.current_h / info.current_w))
    target_size = (target_w, target_h)
    screen = pygame.display.set_mode(target_size, pygame.RESIZABLE)
    recalc_arena(*target_size)
    pygame.display.set_caption("Gladiator Simulation")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("times new roman", 18)
    big_font = pygame.font.SysFont("times new roman", 36)

    def build_backgrounds(size: tuple[int, int]):
        bg_image = pygame.image.load("art/rocks.png").convert()
        bg_scale = 0.5
        scaled_size = (
            max(1, int(bg_image.get_width() * bg_scale)),
            max(1, int(bg_image.get_height() * bg_scale)),
        )
        bg_image = pygame.transform.smoothscale(bg_image, scaled_size)
        bg_surface = pygame.Surface(size)
        tile_w, tile_h = bg_image.get_size()
        for y in range(0, size[1], tile_h):
            for x in range(0, size[0], tile_w):
                bg_surface.blit(bg_image, (x, y))

        wall_image = pygame.image.load(settings.WALL_TEXTURE_PATH).convert()
        wall_texture = build_wall_texture(
            wall_image,
            size,
            settings.WALL_TEXTURE_SCALE,
        )

        sand_image = pygame.image.load(settings.SAND_TEXTURE_PATH).convert()
        sand_texture = build_sand_texture(sand_image, size, settings.SAND_TEXTURE_SCALE)
        return bg_surface, wall_texture, sand_texture

    bg_surface, wall_texture, sand_texture = build_backgrounds(target_size)
    fighter_texture = None
    try:
        fighter_texture = pygame.image.load("art/fighter.png").convert_alpha()
    except Exception:
        fighter_texture = None
    tank_texture = None
    try:
        tank_texture = pygame.image.load("art/tank.png").convert_alpha()
    except Exception:
        tank_texture = None
    archer_texture = None
    try:
        archer_texture = pygame.image.load("art/archer.png").convert_alpha()
    except Exception:
        archer_texture = None
    texture_size = int(settings.GLADIATOR_RADIUS * 2 * settings.GLADIATOR_TEXTURE_SCALE)
    if texture_size > 0:
        if fighter_texture is not None:
            fighter_texture = pygame.transform.smoothscale(fighter_texture, (texture_size, texture_size))
        if tank_texture is not None:
            tank_texture = pygame.transform.smoothscale(tank_texture, (texture_size, texture_size))
        if archer_texture is not None:
            archer_texture = pygame.transform.smoothscale(archer_texture, (texture_size, texture_size))
    def make_grayscale(surface: pygame.Surface) -> pygame.Surface:
        gray = surface.copy()
        try:
            arr = pygame.surfarray.pixels3d(gray)
            lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(arr.dtype)
            arr[:, :, 0] = lum
            arr[:, :, 1] = lum
            arr[:, :, 2] = lum
            del arr
            gray.fill((80, 80, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
        except Exception:
            gray.fill((70, 70, 70, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return gray

    fighter_texture_dead = make_grayscale(fighter_texture) if fighter_texture is not None else None
    tank_texture_dead = make_grayscale(tank_texture) if tank_texture is not None else None
    archer_texture_dead = make_grayscale(archer_texture) if archer_texture is not None else None

    gladiator_count = GLADIATOR_COUNT
    gladiators = spawn_gladiators(gladiator_count)
    projectiles: list[Projectile] = []
    intents: dict = {}
    pending_offers: dict[str, str] = {}
    offer_visuals: list[dict] = []
    team_counter = 1
    max_teams = len(TEAM_SYMBOL_NAMES)
    spade_loop = asyncio.new_event_loop()
    spade_thread = threading.Thread(target=spade_loop.run_forever, daemon=True)
    spade_thread.start()
    arena_agent = None
    gladiator_agents: list = []
    spade_enabled = True
    loading = True
    loading_start = time.time()
    loading_text = LOADING_TEXT

    def start_spade_agents_blocking(label: str):
        nonlocal arena_agent, gladiator_agents, spade_enabled, loading, loading_text, loading_start
        loading_text = label
        loading_start = time.time()
        if not spade_enabled:
            loading = False
            return
        done = threading.Event()

        async def runner():
            nonlocal arena_agent, gladiator_agents, spade_enabled, loading
            try:
                arena_agent, gladiator_agents = await start_agents(
                    gladiator_count,
                    intents,
                    lambda: build_state(
                        gladiators,
                        pending_offers=pending_offers,
                        offer_visuals=offer_visuals,
                        negotiating=engage_delay > 0,
                        negotiation_time_left=engage_delay,
                    ),
                )
            except Exception:
                spade_enabled = False
                arena_agent = None
                gladiator_agents = []
            loading = False
            done.set()

        asyncio.run_coroutine_threadsafe(runner(), spade_loop)
        while not done.is_set():
            render_loading(screen, big_font, 1 + int((time.time() - loading_start) * 4) % 3, loading_text)
            pygame.time.delay(150)
            pygame.event.pump()

    def stop_spade_agents():
        nonlocal arena_agent, gladiator_agents
        if arena_agent or gladiator_agents:
            try:
                future = asyncio.run_coroutine_threadsafe(stop_agents(arena_agent, gladiator_agents), spade_loop)
                future.result(timeout=2)
            except Exception:
                pass
        arena_agent = None
        gladiator_agents = []

    def shutdown_spade_loop():
        try:
            async def _shutdown():
                await stop_agents(arena_agent, gladiator_agents)
                loop = asyncio.get_running_loop()
                tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            future = asyncio.run_coroutine_threadsafe(_shutdown(), spade_loop)
            future.result(timeout=2)
            spade_loop.call_soon_threadsafe(spade_loop.stop)
            spade_thread.join(timeout=2)
        except Exception:
            try:
                spade_loop.call_soon_threadsafe(spade_loop.stop)
                spade_thread.join(timeout=2)
            except Exception:
                pass

    def clear_offers() -> None:
        pending_offers.clear()
        offer_visuals.clear()

    def reset_state(keep_classes: bool, loading_label: str) -> None:
        nonlocal gladiators, loading, finished, started, paused, engage_delay, elapsed
        nonlocal team_counter, betrayal_pending, betrayal_timer, winner_text
        nonlocal betrayal_teams_done_opp, betrayal_teams_done_end, betrayal_global_opp_done

        stop_spade_agents()
        intents.clear()
        clear_offers()
        if keep_classes:
            class_list = [g.class_type for g in gladiators]
            gladiators = spawn_gladiators(gladiator_count, class_list)
        else:
            gladiators = spawn_gladiators(gladiator_count)
        loading = True
        start_spade_agents_blocking(loading_label)
        finished = False
        started = False
        paused = False
        engage_delay = 0.0
        elapsed = 0.0
        team_counter = 1
        betrayal_pending = False
        betrayal_timer = 0.0
        winner_text = None
        betrayal_teams_done_opp.clear()
        betrayal_teams_done_end.clear()
        betrayal_global_opp_done = False

    finished = False
    started = False
    paused = False
    engage_delay = 0.0
    elapsed = 0.0
    running = True
    betrayal_pending = False
    betrayal_timer = 0.0
    winner_text: str | None = None
    betrayal_teams_done_opp: set[int] = set()
    betrayal_teams_done_end: set[int] = set()
    betrayal_global_opp_done = False
    export_button_rect: pygame.Rect | None = None
    export_message_time: float | None = None
    export_message_name: str | None = None

    start_spade_agents_blocking("Loading")

    while running:
        dt = clock.tick(FPS) / 1000.0
        if started and not finished and not paused:
            elapsed += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == KEY_ESCAPE:
                    running = False
                if event.key == KEY_RESTART:
                    reset_state(keep_classes=True, loading_label=RESTARTING_TEXT)
                if event.key == KEY_REFRESH:
                    reset_state(keep_classes=False, loading_label=REFRESHING_TEXT)
                if event.key in KEY_START and not finished:
                    if not started:
                        started = True
                        engage_delay = 10.0
                        clear_offers()
                        team_counter = 1
                        for g in gladiators:
                            g.team_id = None
                            g.has_betrayed_opp = False
                            g.has_betrayed_end = False
                            g.last_team_change = None
                        paused = False
                    else:
                        paused = not paused
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and finished and export_button_rect:
                if export_button_rect.collidepoint(event.pos):
                    os.makedirs("logs", exist_ok=True)
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"logs/results_{timestamp}.csv"
                    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(["winner", winner_text or ""])
                        writer.writerow(["elapsed_seconds", f"{elapsed:.2f}"])
                        writer.writerow([])
                        writer.writerow(
                            [
                                "name",
                                "class",
                                "team",
                                "alive",
                                "hp",
                                "max_hp",
                                "armor",
                                "weapon",
                                "weapon_range",
                                "weapon_damage",
                                "weapon_cooldown",
                                "weapon_ranged",
                            ]
                        )
                        for g in gladiators:
                            writer.writerow(
                                [
                                    g.name,
                                    g.class_type,
                                    g.team_id if g.team_id is not None else "",
                                    "yes" if g.alive else "no",
                                    g.hp,
                                    g.max_hp,
                                    g.armor,
                                    g.weapon.name,
                                    g.weapon.range,
                                    g.weapon.damage,
                                    g.weapon.cooldown,
                                    "yes" if g.weapon.ranged else "no",
                                ]
                            )
                    export_message_time = time.time()
                    export_message_name = os.path.basename(filename)
            if event.type == pygame.VIDEORESIZE:
                target_size = (event.w, event.h)
                screen = pygame.display.set_mode(target_size, pygame.RESIZABLE)
                old_center = settings.ARENA_CENTER.copy()
                old_radius = settings.ARENA_RADIUS
                recalc_arena(*target_size)
                scale = settings.ARENA_RADIUS / max(1, old_radius)
                for g in gladiators:
                    offset = g.position - old_center
                    g.position = settings.ARENA_CENTER + offset * scale
                    g._clamp_to_arena()
                for proj in projectiles:
                    offset = proj.position - old_center
                    proj.position = settings.ARENA_CENTER + offset * scale
                bg_surface, wall_texture, sand_texture = build_backgrounds(target_size)

        if started and not finished and not paused:
            if engage_delay > 0:
                engage_delay = max(0.0, engage_delay - dt)
            negotiating = engage_delay > 0
            if not negotiating:
                clear_offers()
            glad_by_name = {g.name: g for g in gladiators}

            def team_size(team_id: int | None) -> int:
                if team_id is None:
                    return 0
                return sum(1 for g in gladiators if g.team_id == team_id and g.alive)

            def can_create_team() -> bool:
                return team_counter <= max_teams

            team_counts = {}
            for g in gladiators:
                if g.alive and g.team_id is not None:
                    team_counts[g.team_id] = team_counts.get(g.team_id, 0) + 1
            for g in gladiators:
                if not g.alive or g.team_id is None:
                    continue

                team_low = any(
                    mate.alive and mate.team_id == g.team_id and mate.hp / max(1, mate.max_hp) < 0.33
                    for mate in gladiators
                )
                if not team_low:
                    continue

                other_teams = [tid for tid, count in team_counts.items() if tid != g.team_id and count < 3]
                if (
                    other_teams
                    and random.random() < 0.75
                    and not g.has_betrayed_opp
                    and g.team_id is not None
                    and g.team_id not in betrayal_teams_done_opp
                    and not betrayal_global_opp_done
                ):
                    orig_team = g.team_id
                    g.team_id = random.choice(other_teams)
                    g.last_team_change = time.time()
                    g.has_betrayed_opp = True
                    betrayal_teams_done_opp.add(orig_team)
                    betrayal_global_opp_done = True

                    team_counts = {}
                    for gg in gladiators:
                        if gg.alive and gg.team_id is not None:
                            team_counts[gg.team_id] = team_counts.get(gg.team_id, 0) + 1

            now = time.time()
            offer_visuals[:] = [v for v in offer_visuals if v.get("expires", now + 1) > now]

            def upsert_visual(frm: str, to: str, color: tuple[int, int, int], ttl: float):
                expires = time.time() + ttl
                for v in offer_visuals:
                    if v["from"] == frm and v["to"] == to:
                        v["color"] = color
                        v["expires"] = expires
                        return
                offer_visuals.append({"from": frm, "to": to, "color": color, "expires": expires})

            if negotiating:
                for name, entry in list(intents.items()):
                    data = entry.get("data", {})
                    action = data.get("action")
                    if action == "offer":
                        target_name = data.get("target")
                        proposer = glad_by_name.get(name)
                        target = glad_by_name.get(target_name)
                        if proposer and target and proposer.alive and target.alive:

                            proposer_size = team_size(proposer.team_id) or 1
                            target_size = team_size(target.team_id) or 1
                            if proposer_size < 3 and target_size < 3 and (proposer.team_id is None or proposer.team_id != target.team_id):
                                pending_offers[target.name] = proposer.name
                                upsert_visual(proposer.name, target.name, (150, 150, 150), ttl=engage_delay or 2)
                        intents.pop(name, None)
                    elif action == "accept":
                        proposer_name = data.get("target")
                        responder = glad_by_name.get(name)
                        proposer = glad_by_name.get(proposer_name)
                        if (
                            responder
                            and proposer
                            and responder.alive
                            and proposer.alive
                            and pending_offers.get(responder.name) == proposer.name
                        ):
                            proposer_size = team_size(proposer.team_id) or 1
                            responder_size = team_size(responder.team_id) or 1
                            merged = False

                            if proposer.team_id and responder.team_id:
                                if proposer.team_id != responder.team_id and proposer_size + responder_size <= 3:
                                    old_team = proposer.team_id
                                    new_team = responder.team_id
                                    for g in gladiators:
                                        if g.team_id == old_team:
                                            g.team_id = new_team
                                    merged = True
                            elif responder.team_id:
                                if responder_size < 3:
                                    proposer.team_id = responder.team_id
                                    merged = True
                            elif proposer.team_id:
                                if proposer_size < 3:
                                    responder.team_id = proposer.team_id
                                    merged = True
                            else:
                                if can_create_team():
                                    responder.team_id = proposer.team_id = team_counter
                                    team_counter += 1
                                    merged = True
                            pending_offers.pop(responder.name, None)
                            upsert_visual(proposer.name, responder.name, (80, 200, 120) if merged else (200, 70, 70), ttl=1.0)
                        intents.pop(name, None)
                    elif action == "decline":
                        proposer_name = data.get("target")
                        responder = glad_by_name.get(name)
                        proposer = glad_by_name.get(proposer_name)
                        if responder and proposer and pending_offers.get(responder.name) == proposer.name:
                            pending_offers.pop(responder.name, None)
                            upsert_visual(proposer.name, responder.name, (200, 70, 70), ttl=1.0)
                        intents.pop(name, None)

            living = [g for g in gladiators if g.alive]
            alive_team_ids = {g.team_id for g in living if g.team_id is not None}
            solo_alive = [g for g in living if g.team_id is None]
            single_team_only = len(alive_team_ids) == 1 and len(solo_alive) == 0
            should_consider_betrayal = len(living) > 1 and single_team_only and engage_delay <= 0

            if should_consider_betrayal:
                if not betrayal_pending:
                    betrayal_pending = True
                    betrayal_timer = 3.0
                    clear_offers()
                else:
                    betrayal_timer = max(0.0, betrayal_timer - dt)
                    if betrayal_timer <= 0:

                        max_hp = max(g.hp for g in living)
                        eligible = [
                            g
                            for g in living
                            if g.hp == max_hp
                            and sum(1 for t in living if t.hp == max_hp) == 1
                            and not g.has_betrayed_end
                            and g.team_id not in betrayal_teams_done_end
                        ]
                        betrayers = [g for g in eligible if random.random() < 0.50]
                        if betrayers:
                            for b in betrayers:
                                orig_team = b.team_id
                                b.team_id = None
                                b.last_team_change = time.time()
                                b.has_betrayed_end = True
                                if orig_team is not None:
                                    betrayal_teams_done_end.add(orig_team)
                            betrayal_pending = False
                            clear_offers()
                        else:

                            team_id = next(iter(alive_team_ids))
                            finished = True
                            winner_text = f"{team_label(team_id)} wins"
                            betrayal_pending = False
                            clear_offers()
            else:
                betrayal_pending = False
            living = [g for g in gladiators if g.alive]
            if len(living) <= 1:
                finished = True
                if living:
                    lone = living[0]
                    if lone.team_id is not None:
                        winner_text = f"{team_label(lone.team_id)} wins"
                    else:
                        winner_text = f"Champion: {lone.name}"
                else:
                    winner_text = "Everyone fell."
            else:
                alive_names = {g.name for g in living}
                targeting: dict[str, str] = {}
                for name, entry in intents.items():
                    t = entry.get("time", 0)
                    if time.time() - t >= 2.0:
                        continue
                    candidate = entry.get("data")
                    if (
                        candidate
                        and not candidate.get("action")
                        and candidate.get("attack")
                        and candidate.get("target") in alive_names
                    ):
                        targeting[name] = candidate.get("target")
                for gladiator in gladiators:
                    intent_entry = intents.get(gladiator.name) if spade_enabled else None
                    intent = None
                    if intent_entry:
                        t = intent_entry.get("time", 0)
                        if time.time() - t < 2.0:
                            candidate = intent_entry.get("data")

                            if candidate and candidate.get("action"):
                                intent = None
                            elif candidate and candidate.get("target") in alive_names:
                                intent = candidate
                        else:
                            intents.pop(gladiator.name, None)
                    targeted_by = {attacker for attacker, target in targeting.items() if target == gladiator.name}
                    gladiator.update(
                        dt,
                        gladiators,
                        allow_engage=engage_delay <= 0,
                        projectiles=projectiles,
                        intent=intent,
                        targeted_by=targeted_by,
                        allow_shield=engage_delay <= 0 and not betrayal_pending,
                    )
                for proj in projectiles:
                    proj.update(dt)
                projectiles = [p for p in projectiles if p.alive]

        screen.blit(bg_surface, (0, 0))
        draw_arena(screen, wall_texture, sand_texture)
        for proj in projectiles:
            proj.draw(screen)

        draw_offer_lines(screen, offer_visuals, gladiators)
        for gladiator in gladiators:
            gladiator.draw(
                screen,
                font,
                fighter_texture,
                tank_texture,
                archer_texture,
                fighter_texture_dead,
                tank_texture_dead,
                archer_texture_dead,
            )
        if finished:
            winner_label = (winner_text or settings.WINNER_FALLBACK_TEXT).upper()
            winner_text_surf = big_font.render(winner_label, True, (255, 255, 255))
            button_text_surf = font.render("Export", True, (0, 0, 0))
            button_padding_x = 18
            button_padding_y = 8
            button_rect = pygame.Rect(
                0,
                0,
                button_text_surf.get_width() + button_padding_x * 2,
                button_text_surf.get_height() + button_padding_y * 2,
            )
            export_text_surf = None
            if export_message_time and time.time() - export_message_time < 2.5:
                name = export_message_name or "results.csv"
                export_text_surf = font.render(f'Results exported in "{name}"', True, (255, 255, 255))

            spacing_y = 10
            content_w = max(
                winner_text_surf.get_width(),
                button_rect.width,
                export_text_surf.get_width() if export_text_surf else 0,
            )
            content_h = winner_text_surf.get_height() + button_rect.height
            if export_text_surf:
                content_h += spacing_y + export_text_surf.get_height()
            content_h += spacing_y

            panel_padding_x = 26
            panel_padding_y = 18
            panel_rect = pygame.Rect(
                0,
                0,
                content_w + panel_padding_x * 2,
                content_h + panel_padding_y * 2,
            )
            panel_rect.center = (settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2)
            draw_wood_panel(screen, panel_rect, radius=12)

            y = panel_rect.top + panel_padding_y
            winner_rect = winner_text_surf.get_rect(midtop=(panel_rect.centerx, y))
            screen.blit(winner_text_surf, winner_rect)

            y = winner_rect.bottom + spacing_y
            button_rect.midtop = (panel_rect.centerx, y)
            pygame.draw.rect(screen, (255, 255, 255), button_rect, border_radius=8)
            screen.blit(button_text_surf, button_text_surf.get_rect(center=button_rect.center))
            export_button_rect = button_rect

            if export_text_surf:
                y = button_rect.bottom + spacing_y
                export_rect = export_text_surf.get_rect(midtop=(panel_rect.centerx, y))
                screen.blit(export_text_surf, export_rect)
        else:
            export_button_rect = None

        draw_timer(screen, font, elapsed)

        pygame.display.flip()

    spade_enabled = False
    shutdown_spade_loop()
    pygame.quit()
    return


if __name__ == "__main__":
    run()
