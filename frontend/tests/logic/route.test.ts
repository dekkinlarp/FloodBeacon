import { describe, expect, it } from 'vitest';
import { parseRoute, teamViewHref } from '../../src/logic/route';

describe('parseRoute', () => {
  it('opens the team view for #/team/<id>', () => {
    expect(parseRoute('#/team/TEAM-02')).toEqual({ page: 'team', teamId: 'TEAM-02' });
    expect(parseRoute(teamViewHref('TEAM-05'))).toEqual({ page: 'team', teamId: 'TEAM-05' });
  });

  it('falls back to dispatch for anything else', () => {
    for (const hash of ['', '#', '#/', '#/team/', '#/team/a/b', '#/teams/TEAM-01', '#/team/<script>']) {
      expect(parseRoute(hash), hash).toEqual({ page: 'dispatch' });
    }
  });
});
