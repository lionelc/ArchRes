"""Cells, arms and designs: what a case declares, and how an arm's command line and environment are built.

  Cell    one measured command: id, argv with placeholders {D} (the seed's data dir) and {S} (the state), family,
          factors, an optional role ('P' = in a fix's precondition set, 'control') and, for replication panels, the
          state and setting the cell-setting is bound to
  Arm     one connection of a round: a name written into the run files (e.g. 'gd', 'ud'), the engine key, how the
          binary is called ('dir': <path>/<argv[0]> argv[1:], per-utility binaries; 'multicall': <path> argv), and extra
          environment (e.g. a fix's switch)
  Design  the arms, the round orders (from celltest.orders), reps per block, warm-ups per block, the states (their
          environment), the base environment, the reference arm for output checks, and arm groups that must agree"""
from dataclasses import dataclass, field


@dataclass
class Cell:
    id: str
    argv: list
    family: str = None
    factors: dict = field(default_factory=dict)
    role: str = None
    state: str = None
    setting: str = None
    meta: dict = field(default_factory=dict)

    @property
    def key(self):
        """The replication-panel key '<state>|<cell>|<setting>' (cu1's rep format)."""
        return f'{self.state}|{self.id}|{self.setting}'


@dataclass
class Arm:
    name: str
    engine: str
    kind: str          # 'dir' | 'multicall'
    path: str
    env: dict = field(default_factory=dict)

    def binary(self, argv):
        return f'{self.path}/{argv[0]}' if self.kind == 'dir' else self.path

    def command(self, argv):
        return [f'{self.path}/{argv[0]}'] + list(argv[1:]) if self.kind == 'dir' else [self.path] + list(argv)


@dataclass
class Design:
    arms: list
    orders: list
    reps: int = 3
    warmup: int = 0
    states: dict = field(default_factory=lambda: {'C': {'LC_ALL': 'C'}})
    base_env: dict = field(default_factory=lambda: {'PATH': '/usr/bin:/bin'})
    ref_arm: str = None
    agree: list = field(default_factory=list)   # groups of arm names that must produce identical output

    def arm(self, name):
        return next(a for a in self.arms if a.name == name)


def substitute(argv, data_dir, state):
    return [x.replace('{D}', data_dir).replace('{S}', state) for x in argv]


def command_env(design, arm, cell, data_dir, state):
    """The exact argv and environment of one arm on one cell in one state."""
    argv = substitute(cell.argv, data_dir, state)
    env = dict(design.base_env); env.update(design.states[state]); env.update(arm.env)
    return arm.command(argv), env
