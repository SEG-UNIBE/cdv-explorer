// Shared tooltip positioning. Places the tooltip to the right of the cursor by
// default, but flips it to the left when it would overflow the right edge of the
// viewport (so it stays readable near the right side of the display). Also clamps
// vertically so it never spills off the top or bottom.
//
// Accepts either a raw DOM node or a d3 selection as `target`.
export function positionTooltip(target, pageX, pageY, options = {}) {
  const node = target && typeof target.node === 'function' ? target.node() : target;
  if (!node) {
    return;
  }

  const { offsetX = 10, offsetY = 28, margin = 8 } = options;
  const rect = node.getBoundingClientRect();
  const docEl = document.documentElement;
  const viewportWidth = docEl.clientWidth;
  const viewportHeight = docEl.clientHeight;
  const scrollX = window.scrollX || window.pageXOffset || 0;
  const scrollY = window.scrollY || window.pageYOffset || 0;

  let left = pageX + offsetX;
  // Flip to the left of the cursor when the tooltip would overflow the right edge.
  if (left + rect.width > scrollX + viewportWidth - margin) {
    const flipped = pageX - offsetX - rect.width;
    left = flipped >= scrollX + margin ? flipped : scrollX + margin;
  }

  let top = pageY - offsetY;
  if (top + rect.height > scrollY + viewportHeight - margin) {
    top = scrollY + viewportHeight - margin - rect.height;
  }
  if (top < scrollY + margin) {
    top = scrollY + margin;
  }

  node.style.left = `${left}px`;
  node.style.top = `${top}px`;
}
