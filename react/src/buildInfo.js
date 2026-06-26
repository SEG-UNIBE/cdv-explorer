import pkg from '../package.json';

const packageVersion = pkg.version;
const REPOSITORY_URL = 'https://github.com/SEG-UNIBE/cdv-explorer';

const appVersion = import.meta.env.VITE_APP_VERSION || packageVersion;
const commitSha = import.meta.env.VITE_APP_COMMIT_SHA || 'dev';
const fullCommitSha = import.meta.env.VITE_APP_COMMIT_FULL_SHA || commitSha;

function isCommitSha(value) {
  return /^[0-9a-f]{7,40}$/i.test(String(value || ''));
}

export const APP_VERSION = appVersion;
export const APP_COMMIT_SHA = commitSha;
export const APP_COMMIT_FULL_SHA = fullCommitSha;
export const APP_COMMIT_URL = isCommitSha(fullCommitSha)
  ? `${REPOSITORY_URL}/commit/${fullCommitSha}`
  : null;
export const APP_BUILD_LABEL = `v${APP_VERSION} @ ${APP_COMMIT_SHA}`;
