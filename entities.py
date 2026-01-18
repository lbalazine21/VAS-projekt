from __future__ import annotations
import random
import math
import time
import pygame
import settings
TEAM_SYMBOL_NAMES = ["Square", "Diamond", "Triangle", "Star"]

# INICIJALIZIRANJE KLASE ORUŽJA
class Weapon:
    def __init__(self, name: str, damage: int, range_px: float, cooldown: float, ranged: bool = False, projectile_speed: float = 0.0):
        self.name = name
        self.damage = damage
        self.range = range_px
        self.cooldown = cooldown
        self.ranged = ranged
        self.projectile_speed = projectile_speed

# INICIJALIZIRANJE KLASE PROJEKTILA ORUŽJA
class Projectile:
    def __init__(self, position: pygame.Vector2, velocity: pygame.Vector2, damage: int, owner: "Gladiator", target: "Gladiator"):
        self.position = pygame.Vector2(position)
        self.velocity = pygame.Vector2(velocity)
        self.damage = damage
        self.owner = owner
        self.target = target
        self.radius = 5
        self.alive = True

    def update(self, dt: float) -> None:
        if not self.alive:
            return
        self.position += self.velocity * dt
        if not self.target.alive:
            self.alive = False
            return
        if self.position.distance_to(self.target.position) <= self.radius + self.target.radius:
            self._hit(self.target)
            self.alive = False
            return
        if (self.position - settings.ARENA_CENTER).length() > settings.ARENA_RADIUS + 50:
            self.alive = False

    def _hit(self, target: "Gladiator") -> None:
        raw_damage = self.damage + random.randint(-3, 3)
        mitigated = max(1, int(raw_damage - target.armor * 0.25))
        target.apply_damage(mitigated, self.owner)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.alive:
            return
        if self.velocity.length_squared() == 0:
            pygame.draw.circle(surface, (10, 10, 10), self.position, 3)
            return
        dir_vec = self.velocity.normalize()
        tip = self.position + dir_vec * 10
        tail = self.position - dir_vec * 6
        pygame.draw.line(surface, (10, 10, 10), tail, tip, width=2)

# INICIJALIZIRANJE KLASE GLADIJATORA
class Gladiator:
    def __init__(
        self,
        name: str,
        position: tuple[float, float],
        class_type: str,
        hp: int,
        armor: int,
        speed: float,
        weapon: Weapon,
    ):
        self.name = name
        self.class_type = class_type
        self.team_id: int | None = None
        self.position = pygame.Vector2(position)
        self.velocity = pygame.Vector2()
        self.speed = speed
        self.radius = settings.GLADIATOR_RADIUS
        self.hp = hp
        self.max_hp = hp
        self.armor = armor
        self.weapon = weapon
        self.cooldown_timer = 0.0
        self.last_attacker: Gladiator | None = None
        self.retreating = False
        self.sprint_timer = 0.0
        self.retreat_cooldown = 0.0
        self.retreat_uses = 0
        self.wander_timer = random.uniform(0.8, 2.0)
        self.wander_dir = self._random_dir()
        self.last_hit_time = 0.0
        self.kite_timer = 0.0
        self.kite_dir = pygame.Vector2()
        self.last_team_change: float | None = None
        self.has_betrayed_opp = False
        self.has_betrayed_end = False
        self.shield_active = False
        self.shield_timer = 0.0
        self.shield_cooldown = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def distance_to(self, other: "Gladiator") -> float:
        return self.position.distance_to(other.position)

    def update(
        self,
        dt: float,
        gladiators: list["Gladiator"],
        allow_engage: bool,
        projectiles: list[Projectile],
        intent: dict | None = None,
        targeted_by: set[str] | None = None,
        allow_shield: bool = True,
    ) -> None:
        if not self.alive:
            return

        # AŽURIRANJE VREMENSKIH PARAMETARA
        self.cooldown_timer = max(0.0, self.cooldown_timer - dt)
        if self.retreating:
            self.sprint_timer = max(0.0, self.sprint_timer - dt)
        if self.retreat_cooldown > 0:
            self.retreat_cooldown = max(0.0, self.retreat_cooldown - dt)
        if self.kite_timer > 0:
            self.kite_timer = max(0.0, self.kite_timer - dt)
        if self.shield_cooldown > 0:
            self.shield_cooldown = max(0.0, self.shield_cooldown - dt)
        if self.shield_active:
            self.shield_timer = max(0.0, self.shield_timer - dt)
            if self.shield_timer <= 0:
                self.shield_active = False

        # ODLUKA O AKTIVIRANJU ŠTITA
        if allow_shield and self.class_type in ("Fighter", "Tank") and not self.shield_active and self.shield_cooldown <= 0.0:
            if self._incoming_attack(gladiators, targeted_by or set()):
                duration, cooldown = self._shield_params()
                self.shield_active = True
                self.shield_timer = duration
                self.shield_cooldown = cooldown

        # AKTIVIRANJE POVLAČENJA AGENTA
        if allow_engage:
            should_retreat = self._should_retreat(gladiators)
            if should_retreat and not self.retreating:
                self.retreating = True
                self.sprint_timer = 1.0 if self.class_type == "Archer" else 2.0
                self.retreat_uses += 1
            elif self.retreating and not should_retreat and self.sprint_timer <= 0:
                self.retreating = False
                self.retreat_cooldown = 0.0 if self.class_type == "Archer" else 3.0
        else:
            self.retreating = False

        # PROVJERA POSTOJANJA PROTIVNIKA
        target = None
        if allow_engage:
            if intent and intent.get("target"):
                target = next((g for g in gladiators if g.name == intent.get("target") and g.alive), None)
            if target is None:
                target = self._pick_target(gladiators)
        offset = target.position - self.position if target else pygame.Vector2()
        distance = offset.length()

        # ODREĐIVANJE SMJERA KRETANJA AGENTA
        desired = pygame.Vector2()
        if self.retreating:
            flee_dir = self._flee_direction(gladiators)
            if flee_dir.length_squared() == 0:
                flee_dir = -offset.normalize() if distance > 0 else pygame.Vector2(1, 0)
            desired = flee_dir
        else:
            if self.class_type == "Archer" and self.kite_timer > 0 and self.kite_dir.length_squared() > 0:
                desired = self.kite_dir
            elif target:
                if self.weapon.ranged:
                    attack_thresh = self.weapon.range * 0.9
                else:

                    attack_thresh = self.radius + target.radius + 2
                if distance > attack_thresh:
                    if distance > 0:
                        if intent and intent.get("move"):
                            move_vec = pygame.Vector2(intent["move"])
                            if move_vec.length_squared() > 0:
                                desired = move_vec.normalize()
                            else:
                                desired = offset.normalize()
                        else:
                            desired = offset.normalize()
                else:
                    self._attack(target, projectiles)
            else:
                self.wander_timer -= dt
                if self.wander_timer <= 0:
                    self.wander_dir = self._random_dir()
                    self.wander_timer = random.uniform(0.8, 2.0)
                desired = self.wander_dir

        # ODREĐIVANJE BRZINE KRETANJA AGENTA
        jitter = pygame.Vector2(random.uniform(-0.35, 0.35), random.uniform(-0.35, 0.35))
        speed = self.speed
        if self.retreating and self.sprint_timer > 0:
            speed *= 1.6
        elif self.retreating:
            speed *= 1.2
        elif self.class_type == "Archer" and self.kite_timer > 0:
            speed *= 0.7
        self.velocity = (desired + jitter) * speed

        # RAZDVAJANJE AGENATA
        separation = pygame.Vector2()
        for other in gladiators:
            if other is self or not other.alive:
                continue
            d = self.distance_to(other)
            if 0 < d < self.radius * 2:
                separation += (self.position - other.position) / max(d, 1e-3)
        if separation.length_squared() > 0:
            separation = separation.normalize() * self.speed
            self.velocity = (self.velocity + separation * 0.7) * 0.6
        self.position += self.velocity * dt
        self._clamp_to_arena()

    # ODLUKA O SLJEDEĆEM PROTIVNIKU
    def _pick_target(self, gladiators: list["Gladiator"]) -> "Gladiator | None":
        living = [
            g
            for g in gladiators
            if g is not self and g.alive and (self.team_id is None or g.team_id != self.team_id)
        ]
        if not living:
            return None
        if self.last_attacker and self.last_attacker.alive:
            return self.last_attacker
        return min(living, key=lambda g: self.distance_to(g))

    # ODLUKA O NAPADU PROTIVNIKA
    def _attack(self, target: "Gladiator", projectiles: list[Projectile]) -> None:
        if self.cooldown_timer > 0.0 or not target.alive:
            return
        self.cooldown_timer = self.weapon.cooldown
        if self.weapon.ranged:
            direction = (target.position - self.position)
            if direction.length_squared() == 0:
                direction = self._random_dir()
            velocity = direction.normalize() * self.weapon.projectile_speed
            projectiles.append(Projectile(self.position, velocity, self.weapon.damage, self, target))
            self.kite_dir = -direction.normalize()
            self.kite_timer = 0.2
        else:
            raw_damage = self.weapon.damage + random.randint(-3, 3)
            mitigated = max(1, int(raw_damage - target.armor * 0.25))
            target.apply_damage(mitigated, self)

    # ODLUKA O POVLAČENJU AGENTA
    def _should_retreat(self, gladiators: list["Gladiator"]) -> bool:
        if self.hp <= 0:
            return False
        if self.retreat_uses >= 1 or self.retreat_cooldown > 0:
            return False
        hp_ratio = self.hp / max(1, self.max_hp)
        return hp_ratio <= 0.66

    # IZRAČUN SMJERA POVLAČENJA
    def _flee_direction(self, gladiators: list["Gladiator"]) -> pygame.Vector2:
        away = pygame.Vector2()
        for g in gladiators:
            if g is self or not g.alive:
                continue
            offset = self.position - g.position
            dist = offset.length()
            if dist == 0 or dist > 360:
                continue
            away += offset / max(dist, 1e-3)
        if away.length_squared() > 0:
            return away.normalize()
        return pygame.Vector2()

    # OGRANIČAVANJE KRETANJA AGENATA
    def _clamp_to_arena(self) -> None:
        offset = self.position - settings.ARENA_CENTER
        dist = offset.length()
        limit = settings.ARENA_RADIUS - self.radius
        if dist > limit and dist > 0:
            self.position = settings.ARENA_CENTER + offset.normalize() * limit

    # CRTANJE SVIH TEKSTURA U SIMULACIJI
    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        fighter_texture: pygame.Surface,
        tank_texture: pygame.Surface,
        archer_texture: pygame.Surface,
        fighter_texture_dead: pygame.Surface,
        tank_texture_dead: pygame.Surface,
        archer_texture_dead: pygame.Surface,
    ) -> None:
        if not self.alive:
            if self.class_type == "Fighter":
                texture = fighter_texture_dead
            elif self.class_type == "Tank":
                texture = tank_texture_dead
            else:
                texture = archer_texture_dead
            texture_rect = texture.get_rect(center=(self.position.x, self.position.y))
            surface.blit(texture, texture_rect)
            return
        if self.class_type == "Fighter":
            texture = fighter_texture
        elif self.class_type == "Tank":
            texture = tank_texture
        else:
            texture = archer_texture
        texture_rect = texture.get_rect(center=(self.position.x, self.position.y))
        surface.blit(texture, texture_rect)

        # CRTANJE TRAKE RAZINE ŽIVOTA AGENATA
        bar_width = int(self.radius * 2.6)
        bar_height = 10
        bar_x = self.position.x - bar_width / 2
        bar_y = self.position.y - self.radius - 18
        pygame.draw.rect(surface, (35, 35, 35), (bar_x, bar_y, bar_width, bar_height))
        hp_ratio = max(0.0, min(1.0, self.hp / max(1, self.max_hp)))
        hp_color = (30, 200, 80) if hp_ratio >= 0.66 else (230, 160, 60) if hp_ratio >= 0.33 else (210, 60, 60)
        if self.shield_active:
            gray = int(0.3 * hp_color[0] + 0.59 * hp_color[1] + 0.11 * hp_color[2])
            hp_color = (gray, gray, gray)
        pygame.draw.rect(surface, hp_color, (bar_x, bar_y, bar_width * hp_ratio, bar_height))
        pygame.draw.rect(surface, (0, 0, 0), (bar_x, bar_y, bar_width, bar_height), width=1)

        # ODREĐIVANJE POZICIJA LABELA AGENATA
        if self.team_id:
            symbol_idx = max(0, (self.team_id - 1) % len(TEAM_SYMBOL_NAMES))
            symbol_y = bar_y + bar_height / 2
            symbol_x = bar_x + bar_width + 10
            if self.last_team_change:
                sym_color = (200, 40, 40)
            else:
                sym_color = (20, 20, 20)
            self._draw_symbol(surface, symbol_idx, symbol_x, symbol_y, size=14, color=sym_color)

        name_color = (0, 0, 0)
        label = self.name[1:] if self.name.startswith("G") else self.name
        prev_bold = font.get_bold()
        font.set_bold(True)
        name_text = font.render(label, True, name_color)
        font.set_bold(prev_bold)
        name_rect = name_text.get_rect(midright=(bar_x - 6, bar_y + bar_height / 2))
        surface.blit(name_text, name_rect)

    # CRTANJE SIMBOLA TIMOVA
    def _draw_symbol(self, surface: pygame.Surface, idx: int, cx: float, cy: float, size: int, color: tuple[int, int, int]) -> None:
        shape = idx % len(TEAM_SYMBOL_NAMES)
        width = 0
        if shape == 0:
            rect = pygame.Rect(0, 0, size, size)
            rect.center = (cx, cy)
            pygame.draw.rect(surface, color, rect, width=width)
        elif shape == 1:
            half = size // 2
            points = [
                (cx, cy - half),
                (cx + half, cy),
                (cx, cy + half),
                (cx - half, cy),
            ]
            pygame.draw.polygon(surface, color, points, width=width)
        elif shape == 2:
            half = size // 2
            points = [
                (cx, cy - half),
                (cx + half, cy + half),
                (cx - half, cy + half),
            ]
            pygame.draw.polygon(surface, color, points, width=width)
        else:
            radius = size // 2
            pygame.draw.circle(surface, color, (cx, cy), radius, width=0)

    def _random_dir(self) -> pygame.Vector2:
        angle = random.uniform(0, 2 * math.pi)
        return pygame.Vector2(math.cos(angle), math.sin(angle))

    # PRIMANJE ŠTETE GLADIJATORA
    def apply_damage(self, amount: int, attacker: "Gladiator") -> None:
        if self.shield_active:
            self.shield_active = False
            self.shield_timer = 0.0
            self.last_attacker = attacker
            self.last_hit_time = time.time()
            return
        self.hp -= amount
        self.last_attacker = attacker
        self.last_hit_time = time.time()

    # PROCJENA PRIJETNJE NAPADA
    def _incoming_attack(self, gladiators: list["Gladiator"], targeted_by: set[str]) -> bool:
        for other in gladiators:
            if other is self or not other.alive:
                continue
            if self.team_id is not None and other.team_id == self.team_id:
                continue
            if targeted_by and other.name not in targeted_by:
                continue
            distance = self.distance_to(other)
            if other.weapon.ranged:
                attack_thresh = other.weapon.range * 0.9
            else:
                attack_thresh = self.radius + other.radius + 2
            if distance <= attack_thresh:
                return True
        return False

    # DEFINIRANJE PARAMETARA ŠTITA
    def _shield_params(self) -> tuple[float, float]:
        if self.class_type == "Tank":
            return 0.45, 2.2
        return 0.35, 1.3