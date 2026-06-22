import { Fragment, useEffect, useMemo, useState } from 'react';
import { getClassificationColorMap } from './classificationColors';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { formatProposalLabel, getProposalCommitUrl, getProposalUrl } from './proposalLinks';

const EDGE_PADDING_PERCENT = 8;

function formatDate(value, options) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  const parsed = new Date(`${text}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }

  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    ...options,
  }).format(parsed);
}

function parseEventMoment(event) {
  const timestampText = String(event?.timestamp || '').trim();
  if (timestampText) {
    const parsedTimestamp = Date.parse(timestampText);
    if (!Number.isNaN(parsedTimestamp)) {
      return parsedTimestamp;
    }
  }

  const dateText = String(event?.date || '').trim();
  if (!dateText) {
    return Number.NaN;
  }

  return Date.parse(`${dateText}T00:00:00Z`);
}

function formatEventTime(timestamp) {
  const text = String(timestamp || '').trim();
  const match = text.match(/T(\d{2}:\d{2}(?::\d{2})?)/);
  return match ? match[1] : '';
}

function getEventTitle(event) {
  if (event.kind === 'regime_transition') {
    return String(event.label || 'Regime transition');
  }
  return event.kind === 'creation' ? 'Created' : String(event.label || event.status || 'Status update');
}

function getEventDescription(event) {
  if (event.kind === 'creation') {
    if (event.status) {
      return `Proposal creation. Earliest recorded status: ${event.status}.`;
    }
    return 'Proposal creation.';
  }

  if (event.kind === 'regime_transition') {
    const previousStandard = String(event.previous_standard || '').trim();
    const currentStandard = String(event.standard || '').trim();
    if (event.previous_status && event.previous_status !== event.status) {
      return `Reporting regime changed from ${previousStandard || 'the previous regime'} to ${currentStandard || 'the next regime'}, remapping status from ${event.previous_status} to ${event.status}.`;
    }
    return `Reporting regime changed from ${previousStandard || 'the previous regime'} to ${currentStandard || 'the next regime'} while status remained ${event.status}.`;
  }

  if (event.previous_status && event.previous_status !== event.status) {
    return `Status changed from ${event.previous_status} to ${event.status}.`;
  }

  return `Status recorded as ${event.status}.`;
}

function formatMilestoneLabel(label) {
  const text = String(label || '').trim();
  const match = text.match(/^BIP(\d+) Activation$/i);
  if (match) {
    return `BIP-${match[1]} activation`;
  }
  return text;
}

export function ProposalEventTimeline({
  timeline,
  milestones = [],
}) {
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();
  const [activeEventKey, setActiveEventKey] = useState('');

  const events = useMemo(() => {
    const timelineEvents = Array.isArray(timeline?.events) ? timeline.events : [];
    return timelineEvents.map((event, index) => {
      const sameDayNeighbor = timelineEvents[index - 1]?.date === event?.date
        || timelineEvents[index + 1]?.date === event?.date;

      return {
        ...event,
        key: `${event.kind || 'event'}-${event.date || 'unknown'}-${event.status || event.label || 'unknown'}-${index}`,
        moment: parseEventMoment(event),
        showTime: sameDayNeighbor,
        timeLabel: sameDayNeighbor ? formatEventTime(event.timestamp) : '',
      };
    });
  }, [timeline]);

  useEffect(() => {
    setActiveEventKey(events[0]?.key || '');
  }, [events]);

  const statusColors = useMemo(() => getClassificationColorMap(
    'status',
    Array.from(new Set(events.map((event) => String(event.status || '').trim()).filter(Boolean)))
  ), [events]);

  const eventDomain = useMemo(() => {
    const timestamps = events
      .map((event) => event.moment)
      .filter((value) => !Number.isNaN(value));
    if (!timestamps.length) {
      return null;
    }

    return {
      min: Math.min(...timestamps),
      max: Math.max(...timestamps),
    };
  }, [events]);

  const visibleMilestones = useMemo(() => {
    if (!eventDomain) {
      return [];
    }

    return (Array.isArray(milestones) ? milestones : [])
      .map((milestone) => {
        const dateText = String(milestone?.date || '').trim();
        const timestamp = Date.parse(`${dateText}T00:00:00Z`);
        if (Number.isNaN(timestamp) || timestamp < eventDomain.min || timestamp > eventDomain.max) {
          return null;
        }

        const offset = eventDomain.min === eventDomain.max
          ? 50
          : EDGE_PADDING_PERCENT + ((timestamp - eventDomain.min) / (eventDomain.max - eventDomain.min)) * (100 - EDGE_PADDING_PERCENT * 2);

        let listIndex = -1;
        if (events.length >= 2) {
          let sawEarlierEvent = false;
          for (let index = 0; index < events.length; index += 1) {
            const eventTimestamp = Date.parse(`${events[index].date}T00:00:00Z`);
            if (Number.isNaN(eventTimestamp)) {
              continue;
            }
            if (eventTimestamp < timestamp) {
              sawEarlierEvent = true;
              continue;
            }
            listIndex = sawEarlierEvent ? index : -1;
            break;
          }
        }

        return {
          key: `${dateText}-${String(milestone?.standard || '').trim() || 'milestone'}`,
          label: formatMilestoneLabel(milestone?.label || 'Milestone'),
          offset,
          listIndex,
        };
      })
      .filter(Boolean);
  }, [eventDomain, events, milestones]);

  if (!timeline || !events.length) {
    return null;
  }

  const proposalLabel = formatProposalLabel(timeline.proposal_id, ecosystem);
  const proposalHref = getProposalUrl(timeline.proposal_id, snapshotLabel, { linkMode }, ecosystem);

  const getOffsetPercent = (event) => {
    const timestamp = event.moment;
    if (!eventDomain || Number.isNaN(timestamp)) {
      return 0;
    }
    if (eventDomain.min === eventDomain.max) {
      return 50;
    }

    const normalizedOffset = (timestamp - eventDomain.min) / (eventDomain.max - eventDomain.min);
    return EDGE_PADDING_PERCENT + normalizedOffset * (100 - EDGE_PADDING_PERCENT * 2);
  };

  return (
    <div className="proposal-event-history">
      <div className="proposal-event-history__summary">
        <strong className="proposal-event-history__summary-heading">
          <span>
            {proposalHref !== '#' ? (
              <a
                className="proposal-event-history__summary-link"
                href={proposalHref}
                target="_blank"
                rel="noreferrer"
              >
                {proposalLabel}
              </a>
            ) : proposalLabel}
            {timeline.title ? (
              <span className="proposal-event-history__summary-title"> ({timeline.title})</span>
            ) : null}
          </span>
        </strong>
        <p className="proposal-event-history__summary-copy">
          {events.length} recorded events
          {timeline.created ? ` from ${formatDate(timeline.created, { year: 'numeric', month: 'short', day: 'numeric' })}` : ''}
          {timeline.current_status ? (
            <>
              {', current status '}
              <span className="proposal-event-history__badge">{timeline.current_status}</span>
            </>
          ) : null}
          .
        </p>
      </div>

      <div className="proposal-event-history__plot-wrap">
        <div className="proposal-event-history__plot" role="img" aria-label={`${proposalLabel} event timeline`}>
          <div className="proposal-event-history__axis" />
          {visibleMilestones.map((milestone) => (
            <div
              key={milestone.key}
              className="proposal-event-history__milestone"
              style={{ left: `${milestone.offset}%` }}
              aria-hidden="true"
            >
              <span className="proposal-event-history__milestone-label">
                {milestone.label}
              </span>
            </div>
          ))}
          <div className="proposal-event-history__axis-label is-start">
            {formatDate(events[0]?.date, { year: 'numeric', month: 'short', day: 'numeric' })}
            {events[0]?.timeLabel ? `, ${events[0].timeLabel}` : ''}
          </div>
          <div className="proposal-event-history__axis-label is-end">
            {formatDate(events[events.length - 1]?.date, { year: 'numeric', month: 'short', day: 'numeric' })}
            {events[events.length - 1]?.timeLabel ? `, ${events[events.length - 1].timeLabel}` : ''}
          </div>
          {events.map((event, index) => {
            const color = event.kind === 'creation'
              ? 'var(--chart-focus)'
              : (statusColors[String(event.status || '').trim()] || 'var(--primary-color)');
            const href = getProposalCommitUrl(event.commit, {
              id: timeline.proposal_id,
              fallbackSnapshotLabel: snapshotLabel,
            }, ecosystem);
            const linkLabel = event.commit ? 'Open commit diff' : 'Open historic version';
            const isActive = activeEventKey === event.key;
            const laneClass = index % 2 === 0 ? 'is-above' : 'is-below';

            return (
              <div
                key={event.key}
                className={`proposal-event-history__marker ${laneClass}${isActive ? ' is-active' : ''}`}
                style={{ left: `${getOffsetPercent(event)}%`, '--event-color': color }}
                onMouseEnter={() => setActiveEventKey(event.key)}
              >
                <div className="proposal-event-history__marker-label">
                  <span>{getEventTitle(event)}</span>
                  <span>{formatDate(event.date, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                  {event.timeLabel ? <span className="proposal-event-history__marker-time">{event.timeLabel}</span> : null}
                </div>
                {href !== '#' ? (
                  <a
                    className="proposal-event-history__dot"
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`${linkLabel} for ${proposalLabel} on ${event.date}`}
                    onFocus={() => setActiveEventKey(event.key)}
                  />
                ) : (
                  <span
                    className="proposal-event-history__dot is-disabled"
                    aria-hidden="true"
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="proposal-event-history__list">
        {events.map((event, index) => {
          const href = getProposalCommitUrl(event.commit, {
            id: timeline.proposal_id,
            fallbackSnapshotLabel: snapshotLabel,
          }, ecosystem);
          const linkLabel = event.commit ? 'Open commit diff' : 'Open historic version';
          const isActive = activeEventKey === event.key;
          const color = event.kind === 'creation'
            ? 'var(--chart-focus)'
            : (statusColors[String(event.status || '').trim()] || 'var(--primary-color)');

          return (
            <Fragment key={event.key}>
              {visibleMilestones.filter((milestone) => milestone.listIndex === index).map((milestone) => (
                <div key={milestone.key} className="proposal-event-history__list-milestone" aria-hidden="true">
                  <span>{milestone.label}</span>
                </div>
              ))}
              <article
                className={`proposal-event-history__item${isActive ? ' is-active' : ''}`}
                style={{ '--event-color': color }}
                onMouseEnter={() => setActiveEventKey(event.key)}
              >
                <div className="proposal-event-history__item-date">
                  <span>{formatDate(event.date, { year: 'numeric', month: 'short', day: 'numeric' })}</span>
                  {event.timeLabel ? <span className="proposal-event-history__item-time">{event.timeLabel}</span> : null}
                </div>
                <div className="proposal-event-history__item-body">
                  <div className="proposal-event-history__item-header">
                    <strong>{getEventTitle(event)}</strong>
                  </div>
                  <p>{getEventDescription(event)}</p>
                  <div className="proposal-event-history__item-meta">
                    {event.author ? <span>{event.author}</span> : null}
                    {event.commit ? (
                      href !== '#' ? (
                        <a
                          href={href}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`${linkLabel} ${event.commit.slice(0, 10)} for ${proposalLabel} on ${event.date}`}
                          title={linkLabel}
                        >
                          <code>{event.commit.slice(0, 10)}</code>
                        </a>
                      ) : (
                        <code>{event.commit.slice(0, 10)}</code>
                      )
                    ) : null}
                    {!event.commit && href !== '#' ? (
                      <a href={href} target="_blank" rel="noreferrer">
                        {linkLabel}
                      </a>
                    ) : null}
                  </div>
                </div>
              </article>
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}
