import pygame

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
BG_COLOR = (131, 141, 106)
SAND_COLOR = (200, 185, 130)
FPS = 60
ARENA_RADIUS = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 2 - 80
ARENA_CENTER = pygame.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
GLADIATOR_COUNT = 16

KEY_ESCAPE = pygame.K_ESCAPE
KEY_RESTART = pygame.K_r
KEY_REFRESH = pygame.K_c
KEY_START = (pygame.K_SPACE, pygame.K_RETURN)

LOADING_TEXT_COLOR = (230, 230, 230)
START_TEXT_COLOR = (20, 20, 20)
WIN_TEXT_COLOR = (240, 240, 240)
TIMER_TEXT_COLOR = (10, 10, 10)

LOADING_TEXT = "Loading"
RESTARTING_TEXT = "Restarting"
REFRESHING_TEXT = "Refreshing"
WINNER_FALLBACK_TEXT = "Battle over."
TIMER_TEXT_FORMAT = "Time: {elapsed:0.1f}s"


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
    prev_bold = font.get_bold()
    font.set_bold(True)
    timer_text = font.render(TIMER_TEXT_FORMAT.format(elapsed=elapsed), True, TIMER_TEXT_COLOR)
    font.set_bold(prev_bold)
    timer_rect = timer_text.get_rect(center=(SCREEN_WIDTH // 2, 40))
    surface.blit(timer_text, timer_rect)


def render_loading(surface: pygame.Surface, font: pygame.font.Font, dots: int, label: str) -> None:
    surface.fill((0, 0, 0))
    msg = label + "." * dots
    text = font.render(msg, True, LOADING_TEXT_COLOR)
    rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    surface.blit(text, rect)
    pygame.display.flip()


def draw_winner(surface: pygame.Surface, font: pygame.font.Font, winner_text: str | None) -> None:
    text = (winner_text or WINNER_FALLBACK_TEXT).upper()
    message = font.render(text, True, WIN_TEXT_COLOR)
    rect = message.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
    surface.blit(message, rect)
