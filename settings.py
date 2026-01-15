import pygame

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
SAND_COLOR = (200, 185, 130)
GLADIATOR_RADIUS = 26
GLADIATOR_TEXTURE_SCALE = 1.7
FPS = 60
ARENA_RADIUS = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 2 - 80
ARENA_CENTER = pygame.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
GLADIATOR_COUNT = 16
WALL_TEXTURE_PATH = "art/walls.png"
WALL_TEXTURE_SCALE = 0.1
WALL_TEXTURE_DARKEN = 1.0
SAND_TEXTURE_PATH = "art/sand.png"
SAND_TEXTURE_SCALE = 0.15

KEY_ESCAPE = pygame.K_ESCAPE
KEY_RESTART = pygame.K_r
KEY_REFRESH = pygame.K_c
KEY_START = (pygame.K_SPACE, pygame.K_RETURN)

TIMER_TEXT_COLOR = (245, 245, 245)

LOADING_TEXT = "Loading"
RESTARTING_TEXT = "Restarting"
REFRESHING_TEXT = "Refreshing"
WINNER_FALLBACK_TEXT = "Battle over."
TIMER_TEXT_FORMAT = "Time: {elapsed:0.1f}s"
TIMER_BG_TEXTURE_PATH = "art/wood.png"
TIMER_BG_DARKEN = 0.85

_timer_bg_texture: pygame.Surface | None = None


def build_state(
    gladiators,
    pending_offers: dict | None = None,
    offer_visuals: list | None = None,
    negotiating: bool = False,
    negotiation_time_left: float = 0.0,
) -> dict:
    offers = pending_offers or {}
    visuals = offer_visuals or []
    return {
        "arena_jid": "arena@localhost",
        "negotiating": negotiating,
        "negotiation_time_left": negotiation_time_left,
        "offers": [{"from": v, "to": k} for k, v in offers.items()],
        "offer_visuals": visuals,
        "gladiators": [
            {
                "name": g.name,
                "jid": f"{g.name.lower()}@localhost",
                "pos": [g.position.x, g.position.y],
                "hp": g.hp,
                "armor": g.armor,
                "weapon_range": g.weapon.range,
                "alive": g.alive,
                "team": g.team_id,
            }
            for g in gladiators
        ],
        "arena": {
            "center": [ARENA_CENTER.x, ARENA_CENTER.y],
            "radius": ARENA_RADIUS,
        },
    }


def draw_timer(surface: pygame.Surface, font: pygame.font.Font, elapsed: float) -> None:
    timer_text = font.render(TIMER_TEXT_FORMAT.format(elapsed=elapsed).upper(), True, TIMER_TEXT_COLOR)
    timer_rect = timer_text.get_rect(center=(SCREEN_WIDTH // 2, 40))
    padding_x = 18
    padding_y = 12
    bg_rect = pygame.Rect(
        timer_rect.x - padding_x,
        timer_rect.y - padding_y,
        timer_rect.width + padding_x * 2,
        timer_rect.height + padding_y * 2,
    )
    draw_wood_panel(surface, bg_rect, radius=10)
    surface.blit(timer_text, timer_rect)


def draw_wood_panel(surface: pygame.Surface, rect: pygame.Rect, radius: int = 10) -> None:
    global _timer_bg_texture
    if TIMER_BG_TEXTURE_PATH:
        if _timer_bg_texture is None:
            try:
                _timer_bg_texture = pygame.image.load(TIMER_BG_TEXTURE_PATH).convert()
            except Exception:
                _timer_bg_texture = None
        if _timer_bg_texture is not None:
            tex = pygame.transform.smoothscale(_timer_bg_texture, (rect.width, rect.height))
            if TIMER_BG_DARKEN < 1.0:
                level = max(0, min(255, int(255 * TIMER_BG_DARKEN)))
                tex.fill((level, level, level, 255), special_flags=pygame.BLEND_RGBA_MULT)
            rounded = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            rounded.blit(tex, (0, 0))
            mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            rounded.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(rounded, (rect.x, rect.y))
            return
    pygame.draw.rect(surface, (0, 0, 0), rect, border_radius=radius)


def render_loading(surface: pygame.Surface, font: pygame.font.Font, dots: int, label: str) -> None:
    try:
        bg = pygame.image.load("art/loading.png").convert()
        bg = pygame.transform.smoothscale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.blit(bg, (0, 0))
    except Exception:
        surface.fill((0, 0, 0))
    msg = (label + "." * dots).upper()
    prev_bold = font.get_bold()
    font.set_bold(True)
    text = font.render(msg, True, (0, 0, 0))
    font.set_bold(prev_bold)
    rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 200))
    surface.blit(text, rect)
    pygame.display.flip()
