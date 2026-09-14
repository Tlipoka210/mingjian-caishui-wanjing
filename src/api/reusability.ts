import client from './client';

export const reusabilityApi = {
  getSummary: () => client.get('/reusability/summary'),
  getExternalMetrics: () => client.get('/reusability/external-metrics'),
  getAucDetails: () => client.get('/reusability/auc-details'),
};
