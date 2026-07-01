import { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';

function CandidateNode({ data }) {
  const { label, fullLabel, connections, size, isSource, highlighted, dimmed, selected } = data;

  // Random but stable animation values per node
  const animStyle = useMemo(() => {
    const duration = 3 + Math.random() * 4;
    const delay = Math.random() * -6;
    const drift = 4 + Math.random() * 6;
    return {
      animationDuration: `${duration}s`,
      animationDelay: `${delay}s`,
      '--drift': `${drift}px`,
    };
  }, []);

  // Teal color palette with transparency
  const baseHue = isSource ? 172 : 182;
  const saturation = 38 + Math.min(connections, 12) * 3;
  const lightness = 62 - Math.min(connections, 12) * 2;

  // Adjust alpha based on state
  let alpha;
  if (selected) {
    alpha = 0.95;
  } else if (highlighted) {
    alpha = 0.8;
  } else if (dimmed) {
    alpha = 0.12;
  } else {
    alpha = 0.45 + Math.min(connections, 10) * 0.04;
  }

  const bgColor = `hsla(${baseHue}, ${saturation}%, ${lightness}%, ${alpha})`;

  // Border based on state
  let borderColor, borderWidth;
  if (selected) {
    borderColor = 'rgba(220, 80, 160, 0.85)';
    borderWidth = 3.5;
  } else if (highlighted) {
    borderColor = 'rgba(40, 170, 160, 0.7)';
    borderWidth = 2.5;
  } else if (dimmed) {
    borderColor = 'rgba(150, 180, 180, 0.1)';
    borderWidth = 1;
  } else {
    const borderAlpha = 0.25 + Math.min(connections, 10) * 0.04;
    borderColor = connections > 8
      ? `rgba(170, 80, 155, ${borderAlpha + 0.15})`
      : `rgba(70, 145, 140, ${borderAlpha})`;
    borderWidth = connections > 8 ? 2.5 : 1.5;
  }

  // Shadow based on state
  let boxShadow;
  if (selected) {
    boxShadow = `0 0 0 4px rgba(220, 80, 160, 0.2), 0 6px 25px rgba(60, 140, 140, 0.4), inset 0 1px 12px rgba(255,255,255,0.2)`;
  } else if (highlighted) {
    boxShadow = `0 0 0 3px rgba(40, 170, 160, 0.15), 0 4px 20px rgba(60, 140, 140, 0.35), inset 0 1px 12px rgba(255,255,255,0.15)`;
  } else if (dimmed) {
    boxShadow = 'none';
  } else {
    boxShadow = `0 4px 20px rgba(60, 140, 140, ${alpha * 0.35}), inset 0 1px 12px rgba(255,255,255,0.15)`;
  }

  const nodeSize = selected ? size * 1.15 : highlighted ? size * 1.05 : size;

  return (
    <div
      className={`candidate-node ${dimmed ? '' : 'floating'}`}
      title={`${fullLabel}\nConnections: ${connections}`}
      style={{
        width: nodeSize,
        height: nodeSize,
        borderRadius: '50%',
        background: bgColor,
        border: `${borderWidth}px solid ${borderColor}`,
        backdropFilter: dimmed ? 'none' : 'blur(6px)',
        WebkitBackdropFilter: dimmed ? 'none' : 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        cursor: 'pointer',
        boxShadow,
        transition: 'all 0.35s ease',
        ...animStyle,
        opacity: dimmed ? 0.35 : 1,
        filter: dimmed ? 'grayscale(0.6)' : 'none',
      }}
    >
      {/* Glassy inner highlight */}
      {!dimmed && (
        <div
          style={{
            position: 'absolute',
            top: '12%',
            left: '18%',
            width: '40%',
            height: '35%',
            borderRadius: '50%',
            background: 'radial-gradient(ellipse, rgba(255,255,255,0.35) 0%, transparent 70%)',
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Invisible handles */}
      <Handle
        type="source"
        position={Position.Top}
        style={{ opacity: 0, width: 1, height: 1 }}
      />
      <Handle
        type="target"
        position={Position.Bottom}
        style={{ opacity: 0, width: 1, height: 1 }}
      />

      {/* Label */}
      <span
        className="candidate-label"
        style={{
          position: 'absolute',
          top: nodeSize + 6,
          left: '50%',
          transform: 'translateX(-50%)',
          whiteSpace: 'nowrap',
          fontSize: (selected || highlighted) ? '11px' : nodeSize > 55 ? '10px' : '8.5px',
          fontWeight: (selected || highlighted) ? 700 : connections > 6 ? 600 : 400,
          color: dimmed
            ? 'rgba(120, 150, 150, 0.3)'
            : selected
            ? 'rgba(180, 60, 130, 0.9)'
            : highlighted
            ? 'rgba(30, 100, 100, 0.85)'
            : 'rgba(50, 85, 85, 0.75)',
          fontFamily: "'Inter', sans-serif",
          pointerEvents: 'none',
          userSelect: 'none',
          textShadow: dimmed ? 'none' : '0 1px 3px rgba(255,255,255,0.6)',
          transition: 'all 0.35s ease',
        }}
      >
        {fullLabel}
      </span>
    </div>
  );
}

export default memo(CandidateNode);
