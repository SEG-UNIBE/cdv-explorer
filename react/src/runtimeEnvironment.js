const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);
const REPOSITORY_URL = 'https://github.com/SEG-UNIBE/cdv-explorer';
const DEV_BRANCH_URL = `${REPOSITORY_URL}/tree/dev`;

export function getRuntimeEnvironment(hostname = window.location.hostname) {
  const normalizedHostname = String(hostname || '').trim().toLowerCase();

  if (LOCAL_HOSTS.has(normalizedHostname)) {
    return 'local';
  }

  if (normalizedHostname.endsWith('.pages.dev')) {
    return 'dev';
  }

  return 'prod';
}

export function getEnvironmentBadge(hostname = window.location.hostname) {
  const environment = getRuntimeEnvironment(hostname);

  if (environment === 'local') {
    return 'LOCAL';
  }

  if (environment === 'dev') {
    return 'DEV';
  }

  return 'PROD';
}

export function getRepositoryUrl(hostname = window.location.hostname) {
  return getRuntimeEnvironment(hostname) === 'dev' ? DEV_BRANCH_URL : REPOSITORY_URL;
}

export function getDefaultExperimentalFeaturesEnabled(hostname = window.location.hostname) {
  return getRuntimeEnvironment(hostname) !== 'prod';
}
