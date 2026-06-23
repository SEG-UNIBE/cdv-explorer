const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);

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

  return null;
}

export function getDefaultExperimentalFeaturesEnabled(hostname = window.location.hostname) {
  return getRuntimeEnvironment(hostname) !== 'prod';
}
