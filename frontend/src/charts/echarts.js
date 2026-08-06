// f012 c001 — the ONLY module in the SPA that imports from `echarts`.
//
// Tree-shaken registration (Decision 1): `echarts/core` plus explicit chart and
// component registrations. Never `import * as echarts from 'echarts'` — the full
// bundle roughly doubles the SPA payload and the SPA is PWA-precached (f010 c014),
// so bundle size is a real cost.
//
// The set below is the complete f012 chart inventory, registered once so that
// adding a wave-2 chart never means touching engine wiring:
//   bar/line   — income vs expense trend (c004), budget cycles (c009, c013)
//   line+area  — net worth (c005), stacked account balances (c010)
//   pie        — the ported donut (c001), category breakdowns
//   treemap    — expense breakdown (c006)
//   heatmap    — calendar spend density (c007)
//   sankey     — money flow (c008)
//   gauge      — single-cycle savings goal (c009)
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import {
  BarChart,
  LineChart,
  PieChart,
  TreemapChart,
  HeatmapChart,
  SankeyChart,
  GaugeChart,
} from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  VisualMapComponent,
  CalendarComponent,
  MarkLineComponent,
  MarkPointComponent,
} from 'echarts/components';

let registered = false;

export function registerECharts() {
  if (registered) return;
  use([
    CanvasRenderer,
    BarChart,
    LineChart,
    PieChart,
    TreemapChart,
    HeatmapChart,
    SankeyChart,
    GaugeChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
    VisualMapComponent,
    CalendarComponent,
    MarkLineComponent,
    MarkPointComponent,
  ]);
  registered = true;
}
