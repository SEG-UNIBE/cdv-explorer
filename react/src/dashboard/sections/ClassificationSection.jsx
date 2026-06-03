import { useState } from 'react';
import { TabView, TabPanel } from 'primereact/tabview';
import { ClassificationPieChart } from '../../ClassificationPieChart';
import { ClassificationStackedTimelineChart } from '../../ClassificationStackedTimelineChart';
import { ClassificationChordDiagram } from '../../ClassificationChordDiagram';
import { ClassificationLegend } from '../../ClassificationLegend';
import { ClassificationRelationTable } from '../../ClassificationRelationTable';
import { ExportableCard } from '../ExportableCard';
import { CLASSIFICATION_DIMENSIONS } from '../constants';

function ClassificationContent({
  ecosystem,
  classificationCategoryDomains,
  classificationDistributions,
  classificationTimeline,
  classificationChordData,
  classificationRelationRows,
}) {
  const [includeThirdDim, setIncludeThirdDim] = useState(false);
  const dimensions = ecosystem.classificationDimensions || CLASSIFICATION_DIMENSIONS;

  const hasChordData = dimensions.length >= 2 &&
    dimensions.every(({ field }) => {
      const domain = classificationCategoryDomains[field] || [];
      return domain.some((cat) => cat !== 'Unspecified' && !cat.startsWith('Unknown'));
    });

  const hasDim3 = dimensions.length >= 3;
  const dim3 = dimensions[2];
  const tableRows = includeThirdDim && classificationRelationRows.triplets?.length > 0
    ? classificationRelationRows.triplets
    : classificationRelationRows.pairs;
  const tableDimensions = includeThirdDim && hasDim3
    ? dimensions.slice(0, 3)
    : dimensions.slice(0, 2);

  const dimLabels = dimensions.map((d) => d.label).join(', ');

  return (
    <>
      {dimensions.map((dimension) => (
        <ExportableCard
          key={dimension.field}
          className="mb-4"
          exportTitle={`${ecosystem.proposalShortPlural} by ${dimension.label}`}
        >
          <h3>{ecosystem.proposalShortPlural} by {dimension.label}</h3>
          <div className="dashboard-grid dashboard-grid--classification classification-card__grid">
            <div className="classification-card__panel">
              <ClassificationPieChart
                dimension={dimension.field}
                colorDomain={classificationCategoryDomains[dimension.field]}
                data={classificationDistributions[dimension.field]}
                width={400}
                height={250}
              />
            </div>
            <div className="classification-card__panel classification-card__panel--legend">
              <ClassificationLegend
                dimension={dimension.field}
                colorDomain={classificationCategoryDomains[dimension.field]}
                data={classificationDistributions[dimension.field]}
              />
            </div>
            <div className="classification-card__panel">
              <ClassificationStackedTimelineChart
                categoryDomains={classificationCategoryDomains}
                dimensions={dimensions}
                selectedDimensions={[dimension.field]}
                timelineData={classificationTimeline}
                width={700}
                height={250}
              />
            </div>
          </div>
        </ExportableCard>
      ))}
      {hasChordData && (
        <ExportableCard className="mb-4" style={{ flex: 1 }} exportTitle="Pairwise Classification Chord Diagram">
          <h3>Pairwise Classification</h3>
          <p>This chord diagram shows how {dimLabels} categories co-occur across {ecosystem.proposalShortPlural}.</p>
          <div>
            <ClassificationChordDiagram data={classificationChordData} width={800} height={560} />
          </div>
        </ExportableCard>
      )}
      <ExportableCard className="mb-4" exportTitle="Classification Relation Summary">
        <h3>Classification Relation Summary</h3>
        <p>
          Shows unique {dimensions.slice(0, 2).map((d) => d.label).join('–')} combinations and the number of {ecosystem.proposalShortPlural} that match them.
          {hasDim3 && ` Can be expanded using the optional ${dim3.label} field.`}
        </p>
        {hasDim3 && (
          <div className="classification-relation-toolbar">
            <label className="dependency-filter-checkbox">
              <input
                type="checkbox"
                checked={includeThirdDim}
                onChange={(event) => setIncludeThirdDim(event.target.checked)}
              />
              <span>include {dim3.label}</span>
            </label>
          </div>
        )}
        <ClassificationRelationTable
          rows={tableRows}
          dimensions={tableDimensions}
          proposalShortLabel={ecosystem.acronym || 'IP'}
        />
      </ExportableCard>
    </>
  );
}

export function ClassificationSection({
  ecosystem,
  ecosystemBase,
  selectedSourceIds = [],
  perSourceDashboardData = {},
  classificationCategoryDomains,
  classificationDistributions,
  classificationTimeline,
  classificationChordData,
  classificationRelationRows,
}) {
  const isMultiSource = selectedSourceIds.length > 1;

  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">Classification</h2>
      </div>
      {isMultiSource ? (
        <TabView className="dashboard-source-tabs">
          {selectedSourceIds.map((sourceId) => {
            const source = ecosystemBase?.sources?.[sourceId];
            const data = perSourceDashboardData?.[sourceId];
            if (!source || !data) return null;
            return (
              <TabPanel key={sourceId} header={source.shortLabel || source.acronym}>
                <ClassificationContent
                  ecosystem={{ ...ecosystemBase, ...source }}
                  classificationCategoryDomains={data.classificationCategoryDomains}
                  classificationDistributions={data.classificationDistributions}
                  classificationTimeline={data.classificationTimeline}
                  classificationChordData={data.classificationChordData}
                  classificationRelationRows={data.classificationRelationRows}
                />
              </TabPanel>
            );
          })}
        </TabView>
      ) : (
        <ClassificationContent
          ecosystem={ecosystem}
          classificationCategoryDomains={classificationCategoryDomains}
          classificationDistributions={classificationDistributions}
          classificationTimeline={classificationTimeline}
          classificationChordData={classificationChordData}
          classificationRelationRows={classificationRelationRows}
        />
      )}
    </section>
  );
}
