import type { Event } from '../types';
import { describeEvent } from '../logic/dispatch';
import { eventsToCsv, eventsToJson, exportFileName } from '../logic/exportEvents';
import { downloadText } from './download';

const timeFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Bangkok',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

export function EventLog({ events, limit = 100 }: { events: readonly Event[]; limit?: number }) {
  const latest = events.slice(-limit).reverse();
  return (
    <section className="log" aria-label="Event log">
      <h2 className="panel-title">
        Event log <span className="panel-title__count">{events.length}</span>
        <span className="panel-title__actions">
          <button
            type="button"
            className="btn btn--tiny"
            onClick={() => downloadText(exportFileName(new Date(), 'json'), eventsToJson(events), 'application/json')}
          >
            JSON
          </button>
          <button
            type="button"
            className="btn btn--tiny"
            onClick={() => downloadText(exportFileName(new Date(), 'csv'), eventsToCsv(events), 'text/csv')}
          >
            CSV
          </button>
        </span>
      </h2>
      {latest.length === 0 ? (
        <p className="empty log__empty">No changes yet.</p>
      ) : (
        <ol className="log__list">
          {latest.map((e) => (
            <li key={e.id} className={`log__row log__row--${e.entity_type}`}>
              <time dateTime={e.occurred_at}>{timeFormat.format(new Date(e.occurred_at))}</time>
              <span className="log__text">{describeEvent(e)}</span>
              <span className="log__actor">{e.actor}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
