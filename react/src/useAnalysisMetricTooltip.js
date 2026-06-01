import { useEffect, useRef } from 'react';

export function useAnalysisMetricTooltip() {
  const tooltipRef = useRef(null);

  useEffect(() => {
    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    tooltipRef.current = tooltipNode;
    tooltipNode.className = 'analysis-metric-tooltip';
    Object.assign(tooltipNode.style, {
      position: 'absolute',
      background: 'var(--tooltip-bg)',
      color: 'var(--tooltip-text)',
      padding: '6px 10px',
      borderRadius: '4px',
      border: '1px solid var(--tooltip-border)',
      boxShadow: 'var(--tooltip-shadow)',
      fontSize: '12px',
      pointerEvents: 'none',
      maxWidth: '320px',
      lineHeight: '1.45',
      opacity: '0',
      zIndex: '2000',
    });

    return () => {
      tooltipNode.remove();
      tooltipRef.current = null;
    };
  }, []);

  const showTooltip = (event, description) => {
    const tooltip = tooltipRef.current;
    if (!tooltip || !description) {
      return;
    }

    tooltip.textContent = description;
    tooltip.style.opacity = '1';
    tooltip.style.left = `${event.pageX + 10}px`;
    tooltip.style.top = `${event.pageY - 28}px`;
  };

  const moveTooltip = (event) => {
    const tooltip = tooltipRef.current;
    if (!tooltip || tooltip.style.opacity !== '1') {
      return;
    }

    tooltip.style.left = `${event.pageX + 10}px`;
    tooltip.style.top = `${event.pageY - 28}px`;
  };

  const hideTooltip = () => {
    const tooltip = tooltipRef.current;
    if (!tooltip) {
      return;
    }

    tooltip.style.opacity = '0';
  };

  return {
    showTooltip,
    moveTooltip,
    hideTooltip,
  };
}
