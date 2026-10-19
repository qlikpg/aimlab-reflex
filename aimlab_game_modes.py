"""Camera-independent stationary target modes. All times use one monotonic clock."""
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Mode:
    name: str
    radius: int
    count: int


MODES = {
    'voice': Mode('Glosowy (DAJ)',70,1),
    'classic': Mode('Classic', 70, 1),
    'gridshot': Mode('Gridshot', 70, 3),
    'sixshot': Mode('Sixshot', 30, 6),
    'multishot': Mode('Multishot', 55, 5),
    'spidershot': Mode('Spidershot', 70, 1),
    'trap-spidershot': Mode('Trap-spidershot', 70, 1),
}


@dataclass
class Target:
    id: int
    x: float
    y: float
    radius: float
    activated_at: float | None = None
    active: bool = True
    role: str = 'normal'
    style: str | None = None  # Optional per-target appearance override.


@dataclass(frozen=True)
class Config:
    mode: str = 'classic'
    width: int = 1920
    height: int = 1080
    duration: float = 60
    radius: float | None = None  # Pixels at reference 1920x1080; scaled uniformly.
    active_count: int | None = None
    classic_total: int = 10


@dataclass(frozen=True)
class Shot:
    stamp: float
    result: str
    target: Target
    x: float
    y: float
    error_px: float
    target_age_ms: float
    source: str


def circle_contains(target,x,y):
    return math.hypot(x-target.x,y-target.y) <= target.radius+1e-7


class Game:
    def __init__(self, config=Config(), rng=None, hit_test=None):
        self.config = config
        self.hit_test = hit_test if hit_test is not None else circle_contains
        if config.mode not in MODES:
            raise ValueError('Unknown game mode')
        self.mode = MODES[config.mode]
        if (config.width < 320 or config.height < 240 or not math.isfinite(config.duration)
                or config.duration <= 0 or config.classic_total < 1):
            raise ValueError('Invalid screen dimensions, duration or Classic target count')
        reference_radius = self.mode.radius if config.radius is None else config.radius
        if not math.isfinite(reference_radius) or reference_radius < 5:
            raise ValueError('Target radius must be at least 5 reference pixels')
        self.scale = min(config.width / 1920, config.height / 1080)
        self.radius = max(3., reference_radius * self.scale)
        self.count = self.mode.count if config.active_count is None else config.active_count
        if type(self.count) is not int or not 1 <= self.count <= 24:
            raise ValueError('Active target count must be between 1 and 24')
        if config.mode in ('classic', 'voice', 'spidershot', 'trap-spidershot') and self.count != 1:
            raise ValueError('Classic, Spidershot and Trap-spidershot have exactly one active target')
        self.rng = rng if rng is not None else random.Random()
        # Include target outlines, HUD strips and a minimum gap between visible circles.
        rim = 6
        border = max(12, 24*self.scale)
        self.bounds = (border+self.radius+rim, config.width-1-border-self.radius-rim,
                       max(72, 130*self.scale)+self.radius+rim,
                       config.height-1-max(52, 85*self.scale)-self.radius-rim)
        left, right, top, bottom = self.bounds
        spacing = 2*self.radius + max(12, 18*self.scale)
        if right < left or bottom < top:
            raise ValueError('Too little target space: increase resolution or decrease radius')
        nx = int((right-left)//spacing)+1
        ny = int((bottom-top)//spacing)+1
        self.slots = [(left+(right-left)*ix/max(nx-1, 1), top+(bottom-top)*iy/max(ny-1, 1))
                      for ix in range(nx) for iy in range(ny)]
        if len(self.slots) < self.count:
            raise ValueError(f'Cannot place {self.count} non-overlapping targets: increase space or decrease radius')
        self.center = ((config.width-1)/2, (config.height-1)/2)
        if config.mode == 'trap-spidershot':
            # The active blue circle is tangent to the last projector pixel row.
            self.center = ((config.width-1)/2, config.height-1-self.radius)
        self.sides = [p for p in self.slots if math.dist(p, self.center) >= 2*self.radius+max(12,18*self.scale)]
        if (config.mode in ('spidershot','trap-spidershot')
                and (not self.sides or (config.mode == 'spidershot'
                     and not (left <= self.center[0] <= right and top <= self.center[1] <= bottom)))):
            raise ValueError('Too little space for center and side targets: decrease radius')
        self.targets = []
        self.started_at = None
        self.ended_at = None
        self.last_event = -math.inf
        self.hits = self.misses = self.cycles = 0
        self.hit_times = []
        self.ages = []
        self.outbound = []
        self.returns = []
        self.last_center_hit = self.last_side_hit = None
        self.previous_side = None
        self.next_ready = None
        self.next_id = 1
        self.state = 'idle'

    def _target(self, point, role='normal'):
        style = 'classic' if self.config.mode == 'trap-spidershot' and role == 'center' else None
        target = Target(self.next_id, *point, self.radius, role=role, style=style)
        self.next_id += 1
        self.targets.append(target)
        return target

    def _random_target(self, previous=None):
        occupied = {(t.x,t.y) for t in self.targets if t.active}
        choices = [p for p in self.slots if p not in occupied]
        other = [p for p in choices if p != previous]
        if other:
            choices = other
        self._target(self.rng.choice(choices))

    def start(self, now):
        # A fresh engine also clears IDs, counters, intervals and pending activations.
        fresh = Game(self.config, self.rng, self.hit_test)
        self.__dict__.update(fresh.__dict__)
        self.started_at = now
        self.state = 'running'
        self.voice_ready_at = now
        if self.config.mode == 'voice':
            return
        if self.config.mode in ('spidershot','trap-spidershot'):
            self._target(self.center, 'center')
        else:
            for _ in range(self.count):
                self._random_target()

    def activate_voice(self, stamp, now):
        self.tick(now)
        if (self.config.mode != 'voice' or self.state != 'running' or self.targets
                or not math.isfinite(stamp) or stamp < self.voice_ready_at or stamp > now):
            return False
        self._random_target()
        self.voice_ready_at = now
        return True

    def presented(self, now):
        """Call after imshow/waitKey; newly drawn targets become eligible only now."""
        if self.state == 'running':
            for target in self.targets:
                if target.activated_at is None:
                    target.activated_at = now

    def tick(self, now):
        if self.state != 'running':
            return
        if self.config.mode not in ('classic','voice') and now >= self.started_at+self.config.duration:
            self.finish(self.started_at+self.config.duration)
        elif self.next_ready is not None and now >= self.next_ready:
            self.next_ready = None
            self._random_target()

    def finish(self, now):
        if self.state == 'running':
            self.ended_at = now
            self.state = 'finished'
            for target in self.targets:
                target.active = False

    def fire(self, stamp, u, v, now, source='laser'):
        self.tick(now)
        if (self.state != 'running' or not all(math.isfinite(x) for x in (stamp,u,v,now))
                or stamp < self.started_at or stamp > now or stamp <= self.last_event
                or not 0 <= u <= 1 or not 0 <= v <= 1):
            return None
        self.last_event = stamp  # Even an ignored pending-target event cannot be replayed.
        x,y = u*(self.config.width-1), v*(self.config.height-1)
        eligible = [t for t in self.targets if t.active and t.activated_at is not None and stamp >= t.activated_at]
        # Events over a new, not-yet-presented target must not count as hits OR misses.
        if any(t.active and t not in eligible and self.hit_test(t,x,y) for t in self.targets):
            return None
        if not eligible:
            return None
        matches = [t for t in eligible if self.hit_test(t,x,y)]
        target = min(matches or eligible, key=lambda t: (math.hypot(x-t.x,y-t.y),t.id))
        error = math.hypot(x-target.x,y-target.y)
        shot = Shot(stamp, 'hit' if matches else 'miss', target, x, y, error,
                    (stamp-target.activated_at)*1000, source)
        if not matches:
            self.misses += 1
            return shot
        self.hits += 1
        self.hit_times.append(stamp)
        self.ages.append(shot.target_age_ms)
        target.active = False
        self.targets.remove(target)
        mode = self.config.mode
        if mode in ('classic','voice'):
            if self.hits >= self.config.classic_total:
                self.finish(now)
            elif mode == 'voice':
                self.voice_ready_at = now
            else:
                self.next_ready = now+.6
        elif mode in ('spidershot','trap-spidershot'):
            if target.role == 'center':
                if self.last_side_hit is not None:
                    self.returns.append((stamp-self.last_side_hit)*1000)
                    self.cycles += 1
                    self.last_side_hit = None
                self.last_center_hit = stamp
                previous = getattr(self, 'previous_side', None)
                options = [p for p in self.sides if p != previous] or self.sides
                point = self.rng.choice(options)
                self.previous_side = point
                self._target(point, 'side')
            else:
                self.outbound.append((stamp-self.last_center_hit)*1000)
                self.last_side_hit = stamp
                self._target(self.center, 'center')
        else:
            self._random_target((target.x,target.y))
        return shot

    def metrics(self, now):
        duration = 0 if self.started_at is None else max(0,(self.ended_at if self.ended_at is not None else now)-self.started_at)
        mean = lambda values: sum(values)/len(values) if values else None
        interval = ((self.hit_times[-1]-self.hit_times[0])*1000/(len(self.hit_times)-1)
                    if len(self.hit_times)>1 else None)
        return {'duration_s': duration, 'hits': self.hits, 'misses': self.misses,
                'accuracy_percent': 100*self.hits/(self.hits+self.misses) if self.hits+self.misses else 0,
                'hits_per_second': self.hits/duration if duration else 0,
                'mean_hit_interval_ms': interval, 'mean_target_age_ms': mean(self.ages),
                'mean_center_to_side_ms': mean(self.outbound), 'mean_return_to_center_ms': mean(self.returns),
                'full_cycles': self.cycles}

    def remaining(self, now):
        if self.config.mode in ('classic','voice'):
            return None
        return max(0,self.config.duration-(now-self.started_at)) if self.started_at is not None else self.config.duration
