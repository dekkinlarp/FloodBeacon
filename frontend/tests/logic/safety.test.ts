import { describe, expect, it } from 'vitest';
import {
  BLOCK_ASSIGNMENT_HOURS,
  CHECK_IN_INTERVAL_MINUTES,
  SUGGEST_REST_HOURS,
  checkInState,
  equipmentCheck,
  fatigue,
  formatCheckInAge,
  missedCheckIns,
  requiredEquipment,
} from '../../src/logic/safety';

const now = new Date('2026-10-02T12:00:00+07:00');
const ago = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString();

describe('fatigue', () => {
  it('is ok below the rest limit, rest from it, block above the block limit', () => {
    expect(fatigue({ on_duty_since: ago(60 * (SUGGEST_REST_HOURS - 0.1)) }, now).level).toBe('ok');
    expect(fatigue({ on_duty_since: ago(60 * SUGGEST_REST_HOURS) }, now).level).toBe('rest');
    expect(fatigue({ on_duty_since: ago(60 * BLOCK_ASSIGNMENT_HOURS) }, now).level).toBe('rest');
    expect(fatigue({ on_duty_since: ago(60 * BLOCK_ASSIGNMENT_HOURS + 1) }, now).level).toBe('block');
  });

  it('fills the bar as a share of the block limit, capped at 1', () => {
    expect(fatigue({ on_duty_since: ago(60 * BLOCK_ASSIGNMENT_HOURS / 2) }, now).fraction).toBeCloseTo(0.5);
    expect(fatigue({ on_duty_since: ago(60 * 40) }, now).fraction).toBe(1);
  });

  it('treats off duty (no shift start) as 0 hours', () => {
    expect(fatigue({ on_duty_since: null }, now)).toEqual({ hours: 0, level: 'ok', fraction: 0 });
  });

  it('keeps rest below block', () => {
    expect(SUGGEST_REST_HOURS).toBeLessThan(BLOCK_ASSIGNMENT_HOURS);
  });
});

describe('check-in timer', () => {
  it(`flags a field team after more than ${CHECK_IN_INTERVAL_MINUTES} minutes`, () => {
    expect(checkInState({ status: 'en_route', last_check_in_at: ago(CHECK_IN_INTERVAL_MINUTES) }, now).missed).toBe(false);
    expect(checkInState({ status: 'en_route', last_check_in_at: ago(CHECK_IN_INTERVAL_MINUTES + 1) }, now).missed).toBe(true);
    expect(checkInState({ status: 'on_scene', last_check_in_at: null }, now).missed).toBe(true);
    expect(checkInState({ status: 'returning', last_check_in_at: ago(90) }, now).missed).toBe(true);
  });

  it('does not require check-ins from teams at base', () => {
    for (const status of ['available', 'resting', 'off_duty'] as const) {
      expect(checkInState({ status, last_check_in_at: ago(600) }, now)).toMatchObject({ required: false, missed: false });
    }
  });

  it('lists missed teams, longest overdue (never first) first', () => {
    const teams = [
      { id: 'A', status: 'en_route' as const, last_check_in_at: ago(70) },
      { id: 'B', status: 'on_scene' as const, last_check_in_at: ago(200) },
      { id: 'C', status: 'available' as const, last_check_in_at: ago(500) },
      { id: 'D', status: 'returning' as const, last_check_in_at: null },
      { id: 'E', status: 'en_route' as const, last_check_in_at: ago(5) },
    ];
    expect(missedCheckIns(teams, now).map((m) => m.team.id)).toEqual(['D', 'B', 'A']);
  });
});

describe('required equipment', () => {
  it('combines access type and needs without duplicates', () => {
    expect(requiredEquipment({ access_type: 'boat_only', needs: ['medical', 'evacuation'] })).toEqual([
      'life jackets',
      'first aid kit',
    ]);
    expect(requiredEquipment({ access_type: 'truck', needs: ['power'] })).toEqual([]);
  });

  it('marks what the team carries, ignoring case', () => {
    const check = equipmentCheck(
      { access_type: 'walk_only', needs: ['rescue'] },
      { equipment: ['Wading Poles', 'headlamps'] },
    );
    expect(check).toEqual([
      { item: 'wading poles', carried: true },
      { item: 'life jackets', carried: false },
      { item: 'throw bag', carried: false },
    ]);
  });
});

describe('formatCheckInAge', () => {
  it('shows minutes so a missed check-in never reads as "1h"', () => {
    expect(formatCheckInAge(null)).toBe('never');
    expect(formatCheckInAge(0.4)).toBe('<1 min ago');
    expect(formatCheckInAge(59.9)).toBe('59 min ago');
    expect(formatCheckInAge(108)).toBe('1 h 48 min ago');
    expect(formatCheckInAge(125)).toBe('2 h 05 min ago');
  });
});
