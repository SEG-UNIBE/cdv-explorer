const fs = require('fs');
const Module = require('module');
const path = require('path');


function registerReactSourceHook({ repoRoot }) {
  const reactRoot = path.join(repoRoot, 'react');
  const srcRoot = path.join(reactRoot, 'src');
  const babel = require(require.resolve('@babel/core', { paths: [reactRoot] }));
  const presetEnv = require(require.resolve('@babel/preset-env', { paths: [reactRoot] }));
  const presetReact = require(require.resolve('@babel/preset-react', { paths: [reactRoot] }));

  const defaultJsLoader = Module._extensions['.js'];
  const defaultJsxLoader = Module._extensions['.jsx'] || defaultJsLoader;

  function compileSource(module, filename) {
    const source = fs.readFileSync(filename, 'utf8');
    const { code } = babel.transformSync(source, {
      filename,
      presets: [
        [presetEnv, { targets: { node: 'current' }, modules: 'commonjs' }],
        [presetReact, { runtime: 'automatic' }],
      ],
      babelrc: false,
      configFile: false,
      sourceMaps: 'inline',
    });
    module._compile(code, filename);
  }

  Module._extensions['.js'] = function patchedJsLoader(module, filename) {
    if (filename.startsWith(srcRoot)) {
      compileSource(module, filename);
      return;
    }
    defaultJsLoader(module, filename);
  };

  Module._extensions['.jsx'] = function patchedJsxLoader(module, filename) {
    if (filename.startsWith(srcRoot)) {
      compileSource(module, filename);
      return;
    }
    defaultJsxLoader(module, filename);
  };

  const assetExtensions = ['.scss', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ttf', '.woff', '.woff2'];
  assetExtensions.forEach((extension) => {
    Module._extensions[extension] = function assetLoader(module, filename) {
      module.exports = filename;
    };
  });
}


module.exports = {
  registerReactSourceHook,
};
