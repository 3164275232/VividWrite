const PRACTICE_SAMPLE_LIST = [
  {
    id: 'bar-recycling',
    label: 'Bar chart: UK recycling rates',
    chartType: 'bar',
    imageUrl: '/practice-samples/01_bar_recycling_rates.png?v=279e5bd9',
    fileName: '01_bar_recycling_rates.png',
    deplotText: [
      'TITLE | Household recycling rates in five UK cities, 2015 and 2020',
      'CHART TYPE | Bar chart',
      'City | 2015 | 2020',
      'Bristol | 41.70 | 55.20',
      'Leeds | 35.26 | 48.16',
      'Liverpool | 28.05 | 39.15',
      'Manchester | 30.78 | 46.13',
      'Sheffield | 38.19 | 50.80',
    ].join('<0x0A>'),
  },
  {
    id: 'line-passengers',
    label: 'Line graph: public transport use',
    chartType: 'line',
    imageUrl: '/practice-samples/02_line_daily_passengers.png',
    fileName: '02_line_daily_passengers.png',
    deplotText: [
      'TITLE | Average daily passengers using public transport, 2010-2020',
      'CHART TYPE | Line graph',
      'Year | Bus | Rail | Metro',
      '2010 | 1.8 | 1.1 | 0.8',
      '2012 | 1.9 | 1.3 | 1',
      '2014 | 1.7 | 1.5 | 1.2',
      '2016 | 1.6 | 1.8 | 1.5',
      '2018 | 1.5 | 2 | 1.7',
      '2020 | 1.3 | 2.2 | 1.9',
    ].join('<0x0A>'),
  },
  {
    id: 'pie-spending',
    label: 'Pie chart: household spending',
    chartType: 'pie',
    imageUrl: '/practice-samples/04_pie_household_spending.png',
    fileName: '04_pie_household_spending.png',
    deplotText: [
      'TITLE | Average household expenditure in Canada, 2024',
      'CHART TYPE | Pie chart',
      'Category | Percentage',
      'Housing | 32%',
      'Food | 21%',
      'Transport | 17%',
      'Leisure | 12%',
      'Utilities | 10%',
      'Other | 8%',
    ].join('<0x0A>'),
  },
];

export const PRACTICE_SAMPLES = Object.freeze(
  PRACTICE_SAMPLE_LIST.map((sample) => Object.freeze(sample)),
);

export function getPracticeSample(sampleId) {
  return PRACTICE_SAMPLES.find((sample) => sample.id === sampleId) || null;
}

export async function loadPracticeSample(sampleId, fetchImpl = globalThis.fetch) {
  const sample = getPracticeSample(sampleId);
  if (!sample) {
    throw new Error('The selected practice sample is unavailable.');
  }
  if (typeof fetchImpl !== 'function') {
    throw new Error('This browser cannot load the selected practice sample.');
  }

  const response = await fetchImpl(sample.imageUrl);
  if (!response.ok) {
    throw new Error(`Could not load the practice image (HTTP ${response.status}).`);
  }
  const blob = await response.blob();
  const file = new File([blob], sample.fileName, {
    type: blob.type || 'image/png',
    lastModified: 0,
  });
  return { sample, file };
}
