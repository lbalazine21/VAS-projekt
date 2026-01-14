import asyncio
import json
import random
import time
from typing import Callable
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message


class ArenaAgent(Agent):
    def __init__(self, jid: str, password: str, intents: dict, state_fn: Callable[[], dict], interval: float = 0.5):
        super().__init__(jid, password)
        self.intents = intents
        self.state_fn = state_fn
        self.interval = interval

    async def setup(self):
        self.add_behaviour(self.PushState(self.state_fn, self.interval))
        self.add_behaviour(self.ReceiveIntent(self.intents))

    class PushState(CyclicBehaviour):
        def __init__(self, state_fn: Callable[[], dict], interval: float):
            super().__init__()
            self.state_fn = state_fn
            self.interval = interval

        async def run(self):
            await asyncio.sleep(self.interval)
            state = self.state_fn()
            gladiators = state.get("gladiators", [])
            for g in gladiators:
                msg = Message(to=g["jid"])
                msg.body = json.dumps(state)
                await self.send(msg)

    class ReceiveIntent(CyclicBehaviour):
        def __init__(self, intents: dict):
            super().__init__()
            self.intents = intents

        async def run(self):
            msg = await self.receive(timeout=0.1)
            if msg:
                try:
                    data = json.loads(str(msg.body))
                    name = data.get("name")
                    if name:
                        self.intents[name] = {"data": data, "time": time.time()}
                except Exception:
                    pass


class GladiatorAgent(Agent):
    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.last_offer_time = 0.0
        self.propose_chance = 0.15
        self.accept_chance = 0.25

    async def setup(self):
        self.add_behaviour(self.PlanBehaviour())

    class PlanBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if not msg:
                return
            try:
                data = json.loads(str(msg.body))
            except Exception:
                return
            me = None
            enemies = []
            for g in data.get("gladiators", []):
                if g.get("jid") == str(self.agent.jid):
                    me = g
                else:
                    enemies.append(g)
            if not me or not enemies:
                return
            negotiating = data.get("negotiating", False)
            my_pos = me["pos"]
            my_team = me.get("team")

            if negotiating:
                offers = data.get("offers", [])

                for off in offers:
                    if off.get("to") == me["name"]:
                        if random.random() < self.agent.accept_chance:
                            intent = {"name": me["name"], "action": "accept", "target": off.get("from")}
                        else:
                            intent = {"name": me["name"], "action": "decline", "target": off.get("from")}
                        reply = Message(to=data.get("arena_jid", "arena@localhost"))
                        reply.body = json.dumps(intent)
                        await self.send(reply)
                        return

                if (
                    time.time() - getattr(self.agent, "last_offer_time", 0.0) > 1.0
                    and random.random() < self.agent.propose_chance
                ):

                    candidates = [e for e in enemies if e.get("alive") and e.get("team") is None]
                    if candidates:
                        target = random.choice(candidates)
                        intent = {"name": me["name"], "action": "offer", "target": target["name"]}
                        reply = Message(to=data.get("arena_jid", "arena@localhost"))
                        reply.body = json.dumps(intent)
                        await self.send(reply)
                        self.agent.last_offer_time = time.time()
                return

            filtered_enemies = [
                e for e in enemies if e.get("alive") and (my_team is None or e.get("team") != my_team)
            ]
            if not filtered_enemies:
                return

            def dist_sq(e):
                dx = e["pos"][0] - my_pos[0]
                dy = e["pos"][1] - my_pos[1]
                return dx * dx + dy * dy

            target = min(filtered_enemies, key=dist_sq)
            dx = target["pos"][0] - my_pos[0]
            dy = target["pos"][1] - my_pos[1]
            attack = (dx * dx + dy * dy) ** 0.5 <= me["weapon_range"]
            intent = {
                "name": me["name"],
                "move": [dx, dy],
                "attack": attack,
                "target": target["name"],
            }
            reply = Message(to=data.get("arena_jid", "arena@localhost"))
            reply.body = json.dumps(intent)
            await self.send(reply)


async def start_agents(count: int, intents: dict, state_fn: Callable[[], dict]):

    arena_agent = ArenaAgent("arena@localhost", "gladiator", intents=intents, state_fn=state_fn, interval=0.5)
    await arena_agent.start()
    gladiators = []
    for idx in range(count):
        jid = f"g{idx + 1}@localhost"
        agent = GladiatorAgent(jid, "gladiator")
        await agent.start()
        gladiators.append(agent)
    return arena_agent, gladiators


async def stop_agents(arena_agent: Agent | None, gladiators: list[Agent]):
    if arena_agent:
        await arena_agent.stop()
    for agent in gladiators:
        await agent.stop()