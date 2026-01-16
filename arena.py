import math
import random
import pygame
import settings
from entities import Gladiator, Weapon


# DEFINIRANJE RJEČNIKA KLASA
CLASS_CONFIGS = {
    "Archer": {
        "hp": 75,
        "armor": 6,
        "speed": 125.0,
        "weapon": Weapon("Bow", damage=18, range_px=240, cooldown=1.1, ranged=True, projectile_speed=520.0),
    },
    "Fighter": {
        "hp": 100,
        "armor": 12,
        "speed": 110.0,
        "weapon": Weapon("Sword", damage=26, range_px=70, cooldown=1.0),
    },
    "Tank": {
        "hp": 120,
        "armor": 25,
        "speed": 90.0,
        "weapon": Weapon("Axe", damage=32, range_px=65, cooldown=1.2),
    },
}


def team_label(team_id: int | None) -> str:
    from entities import TEAM_SYMBOL_NAMES

    if team_id is None:
        return "Team"
    if 1 <= team_id <= len(TEAM_SYMBOL_NAMES):
        return f"{TEAM_SYMBOL_NAMES[team_id - 1]} team"
    return f"Team {team_id}"


# IZRAČUNAVANJE DIMENZIJA ARENE
def recalc_arena(width: int, height: int) -> int:
    settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT = width, height
    settings.ARENA_CENTER.update(width / 2, height / 2 + 30)
    margin = 140
    settings.ARENA_RADIUS = max(120, min(width, height) // 2 - margin)
    return settings.ARENA_RADIUS


# CRTANJE GLADIJATORSKE ARENE
def draw_arena(
    surface: pygame.Surface,
    wall_texture: pygame.Surface,
    sand_texture: pygame.Surface,
) -> None:
    wall_width = 54
    brick_outer_radius = settings.ARENA_RADIUS + wall_width + 12
    brick_inner_radius = brick_outer_radius - wall_width

    surface.blit(sand_texture, (0, 0))
    surface.blit(wall_texture, (0, 0))


# KREIRANJE TEKSTURE ZIDA
def build_wall_texture(
    texture: pygame.Surface,
    size: tuple[int, int],
    scale: float = 1.0,
) -> pygame.Surface:
    wall_width = 54
    brick_outer_radius = settings.ARENA_RADIUS + wall_width + 12
    brick_inner_radius = brick_outer_radius - wall_width
    if scale != 1.0:
        scaled_size = (
            max(1, int(texture.get_width() * scale)),
            max(1, int(texture.get_height() * scale)),
        )
        texture = pygame.transform.smoothscale(texture, scaled_size)

    tiled = pygame.Surface(size, pygame.SRCALPHA)
    tile_w, tile_h = texture.get_size()
    for y in range(0, size[1], tile_h):
        for x in range(0, size[0], tile_w):
            tiled.blit(texture, (x, y))

    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), settings.ARENA_CENTER, brick_outer_radius)
    pygame.draw.circle(mask, (0, 0, 0, 0), settings.ARENA_CENTER, brick_inner_radius)
    tiled.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tiled


# KREIRANJE TEKSTURE PIJESKA
def build_sand_texture(texture: pygame.Surface, size: tuple[int, int], scale: float = 1.0) -> pygame.Surface:
    wall_width = 54
    brick_outer_radius = settings.ARENA_RADIUS + wall_width + 12
    brick_inner_radius = brick_outer_radius - wall_width
    if scale != 1.0:
        scaled_size = (
            max(1, int(texture.get_width() * scale)),
            max(1, int(texture.get_height() * scale)),
        )
        texture = pygame.transform.smoothscale(texture, scaled_size)

    tiled = pygame.Surface(size, pygame.SRCALPHA)
    tile_w, tile_h = texture.get_size()
    for y in range(0, size[1], tile_h):
        for x in range(0, size[0], tile_w):
            tiled.blit(texture, (x, y))

    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), settings.ARENA_CENTER, brick_inner_radius)
    tiled.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tiled


# POSTAVLJANJE GLADIJATORA UNUTAR ARENE
def spawn_gladiators(count: int, class_list: list[str] | None = None) -> list[Gladiator]:
    gladiators: list[Gladiator] = []
    edge_radius = settings.ARENA_RADIUS - 60
    for idx in range(count):
        angle = 2 * math.pi * idx / count
        pos = settings.ARENA_CENTER + pygame.Vector2(math.cos(angle), math.sin(angle)) * edge_radius
        if class_list and idx < len(class_list):
            class_name = class_list[idx]
        else:
            class_name = random.choice(list(CLASS_CONFIGS.keys()))
        cfg = CLASS_CONFIGS.get(class_name, random.choice(list(CLASS_CONFIGS.values())))
        gladiators.append(
            Gladiator(
                name=f"G{idx + 1}",
                position=pos,
                class_type=class_name,
                hp=cfg["hp"],
                armor=cfg["armor"],
                speed=cfg["speed"],
                weapon=cfg["weapon"],
            )
        )
    return gladiators


def draw_offer_lines(surface: pygame.Surface, offer_visuals: list, gladiators: list[Gladiator]) -> None:
    for v in offer_visuals:
        frm = next((g for g in gladiators if g.name == v["from"]), None)
        to = next((g for g in gladiators if g.name == v["to"]), None)
        if frm and to and frm.alive and to.alive:
            pygame.draw.line(surface, v["color"], frm.position, to.position, width=3)