const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);
const REPOSITORY_URL = 'https://github.com/SEG-UNIBE/cdv-explorer';
const DEV_BRANCH_URL = `${REPOSITORY_URL}/tree/dev`;

function getCurrentHostname(hostname) {
  if (hostname !== undefined) {
    return hostname;
  }

  if (typeof window !== 'undefined' && window.location) {
    return window.location.hostname;
  }

  return '';
}

export function getRuntimeEnvironment(hostname) {
  const currentHostname = getCurrentHostname(hostname);
  const normalizedHostname = String(currentHostname || '').trim().toLowerCase();

  if (LOCAL_HOSTS.has(normalizedHostname)) {
    return 'local';
  }

  if (normalizedHostname.endsWith('.pages.dev')) {
    return 'dev';
  }

  return 'prod';
}

export function getEnvironmentBadge(hostname) {
  const environment = getRuntimeEnvironment(hostname);

  if (environment === 'local') {
    return 'LOCAL';
  }

  if (environment === 'dev') {
    return 'DEV';
  }

  return 'PROD';
}

export function getRepositoryUrl(hostname) {
  return getRuntimeEnvironment(hostname) === 'dev' ? DEV_BRANCH_URL : REPOSITORY_URL;
}

export function getDefaultExperimentalFeaturesEnabled(hostname) {
  return getRuntimeEnvironment(hostname) !== 'prod';
}
