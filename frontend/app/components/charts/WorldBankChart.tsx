"use client";

import React, { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// Chart data item from backend
export interface ChartDataItem {
  name: string;
  code: string;
  value: number;
  formatted_value: string;
  year: string;
  category: string;
}

// Chart data organized by category
export interface ChartByCategory {
  [category: string]: ChartDataItem[];
}

interface WorldBankChartProps {
  country: string;
  chartData: ChartDataItem[];
  chartByCategory: ChartByCategory;
  dataPeriod?: string;
}

// Unit types for grouping indicators with compatible scales
type UnitType =
  | "percentage"
  | "currency_large"
  | "currency_small"
  | "index"
  | "count"
  | "rate"
  | "other";

interface UnitGroup {
  type: UnitType;
  label: string;
  suffix: string;
  items: ChartDataItem[];
}

// Color palette for different categories
const CATEGORY_COLORS: Record<string, string> = {
  economic: "#3b82f6", // blue
  social: "#10b981", // green
  infrastructure: "#8b5cf6", // purple
  governance: "#f59e0b", // amber
  environment: "#06b6d4", // cyan
  conflict_risk: "#ef4444", // red
  other: "#6b7280", // gray
};

// Readable category names
const CATEGORY_LABELS: Record<string, string> = {
  economic: "Economic",
  social: "Social",
  infrastructure: "Infrastructure",
  governance: "Governance",
  environment: "Environment",
  conflict_risk: "Conflict Risk",
  other: "Other",
};

// Determine unit type from indicator code and formatted value
function getUnitType(item: ChartDataItem): UnitType {
  const code = item.code;
  const formatted = item.formatted_value;
  const value = Math.abs(item.value);

  // Percentage indicators (codes ending in ZS or ZG, or formatted with %)
  if (code.includes(".ZS") || code.includes(".ZG") || formatted.includes("%")) {
    return "percentage";
  }

  // Governance indices (estimate scores, usually -2.5 to 2.5)
  if (code.includes(".EST")) {
    return "index";
  }

  // Large currency values (GDP, etc.) - typically in billions/trillions
  if (
    formatted.includes("$") &&
    (formatted.includes("T") || formatted.includes("B"))
  ) {
    return "currency_large";
  }

  // Smaller currency values
  if (formatted.includes("$") && formatted.includes("M")) {
    return "currency_small";
  }

  // Per capita or rate values
  if (code.includes(".PC") || code.includes(".P2") || code.includes(".P5")) {
    return "rate";
  }

  // Population and other large counts
  if (value > 1000000) {
    return "count";
  }

  return "other";
}

// Group data by unit type
function groupByUnitType(data: ChartDataItem[]): UnitGroup[] {
  const groups: Record<UnitType, ChartDataItem[]> = {
    percentage: [],
    currency_large: [],
    currency_small: [],
    index: [],
    count: [],
    rate: [],
    other: [],
  };

  data.forEach((item) => {
    const unitType = getUnitType(item);
    groups[unitType].push(item);
  });

  const unitLabels: Record<UnitType, { label: string; suffix: string }> = {
    percentage: { label: "Percentages", suffix: "%" },
    currency_large: { label: "Economic Value (USD)", suffix: "" },
    currency_small: { label: "Economic Value (Millions USD)", suffix: "" },
    index: { label: "Governance Indices", suffix: "" },
    count: { label: "Population & Counts", suffix: "" },
    rate: { label: "Rates (per capita/100)", suffix: "" },
    other: { label: "Other Indicators", suffix: "" },
  };

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([type, items]) => ({
      type: type as UnitType,
      label: unitLabels[type as UnitType].label,
      suffix: unitLabels[type as UnitType].suffix,
      items,
    }));
}

// Custom tooltip component
const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload as ChartDataItem;
    return (
      <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg max-w-xs z-50">
        <p className="font-semibold text-sm text-gray-900 mb-1">{data.name}</p>
        <p className="text-lg font-bold text-blue-600">{data.formatted_value}</p>
        <p className="text-xs text-gray-500 mt-1">Year: {data.year}</p>
        <p className="text-xs text-gray-400">Code: {data.code}</p>
      </div>
    );
  }
  return null;
};

// Format axis tick labels
const formatAxisLabel = (name: string): string => {
  if (name.length > 25) {
    return name.substring(0, 22) + "...";
  }
  return name;
};

// Format value for axis display
const formatAxisValue = (value: number, unitType: UnitType): string => {
  if (unitType === "percentage") {
    return `${value.toFixed(0)}%`;
  }
  if (unitType === "index") {
    return value.toFixed(1);
  }
  if (unitType === "currency_large") {
    if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
    if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
    return `$${(value / 1e6).toFixed(0)}M`;
  }
  if (unitType === "count") {
    if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
    if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
    if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
    return value.toFixed(0);
  }
  return value.toLocaleString();
};

// Single chart component for a unit group
const UnitGroupChart: React.FC<{ group: UnitGroup }> = ({ group }) => {
  const chartHeight = Math.max(120, group.items.length * 35);

  return (
    <div className="mb-6">
      <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-blue-500"></span>
        {group.label}
        <span className="text-xs font-normal text-gray-400">
          ({group.items.length} indicator{group.items.length > 1 ? "s" : ""})
        </span>
      </h4>
      <div style={{ height: chartHeight }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={group.items}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              horizontal={true}
              vertical={false}
            />
            <XAxis
              type="number"
              tick={{ fontSize: 10 }}
              tickFormatter={(value: number) => formatAxisValue(value, group.type)}
              domain={group.type === "index" ? [-2.5, 2.5] : undefined}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={115}
              tick={{ fontSize: 10 }}
              tickFormatter={formatAxisLabel}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={25}>
              {group.items.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={CATEGORY_COLORS[entry.category] || CATEGORY_COLORS.other}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

const WorldBankChart: React.FC<WorldBankChartProps> = ({
  country,
  chartData,
  chartByCategory,
  dataPeriod,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  // Get available categories
  const categories = Object.keys(chartByCategory).filter(
    (cat) => chartByCategory[cat] && chartByCategory[cat].length > 0
  );

  // Get data to display based on selected category
  const displayData = useMemo(() => {
    return selectedCategory === "all"
      ? chartData
      : chartByCategory[selectedCategory] || [];
  }, [selectedCategory, chartData, chartByCategory]);

  // Group data by unit type for separate charts
  const unitGroups = useMemo(() => groupByUnitType(displayData), [displayData]);

  if (!chartData || chartData.length === 0) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg text-center text-gray-500">
        No chart data available
      </div>
    );
  }

  return (
    <div className="world-bank-chart bg-white rounded-lg border border-gray-200 p-4 mt-4">
      {/* Header */}
      <div className="mb-4">
        <h3 className="text-lg font-bold text-gray-900">
          📊 World Bank Indicators - {country}
        </h3>
        {dataPeriod && (
          <p className="text-sm text-gray-500">Data period: {dataPeriod}</p>
        )}
      </div>

      {/* Category Filter */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setSelectedCategory("all")}
          className={`px-3 py-1 text-xs rounded-full transition-colors ${
            selectedCategory === "all"
              ? "bg-blue-600 text-white"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
          }`}
        >
          All ({chartData.length})
        </button>
        {categories.map((category) => (
          <button
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              selectedCategory === category
                ? "text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
            style={{
              backgroundColor:
                selectedCategory === category
                  ? CATEGORY_COLORS[category] || CATEGORY_COLORS.other
                  : undefined,
            }}
          >
            {CATEGORY_LABELS[category] || category} (
            {chartByCategory[category]?.length || 0})
          </button>
        ))}
      </div>

      {/* Charts grouped by unit type */}
      <div className="space-y-2">
        {unitGroups.map((group) => (
          <UnitGroupChart key={group.type} group={group} />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t flex flex-wrap gap-3 justify-center">
        {categories.map((category) => (
          <div key={category} className="flex items-center gap-1 text-xs">
            <span
              className="w-3 h-3 rounded-sm"
              style={{
                backgroundColor:
                  CATEGORY_COLORS[category] || CATEGORY_COLORS.other,
              }}
            />
            <span className="text-gray-600">
              {CATEGORY_LABELS[category] || category}
            </span>
          </div>
        ))}
      </div>

      {/* Data table for details */}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm text-blue-600 hover:text-blue-800">
          View detailed data table
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-2 py-1 text-left font-medium text-gray-600">
                  Indicator
                </th>
                <th className="px-2 py-1 text-right font-medium text-gray-600">
                  Value
                </th>
                <th className="px-2 py-1 text-center font-medium text-gray-600">
                  Year
                </th>
                <th className="px-2 py-1 text-left font-medium text-gray-600">
                  Category
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {displayData.map((item, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-2 py-1 text-gray-900">{item.name}</td>
                  <td className="px-2 py-1 text-right font-medium text-gray-900">
                    {item.formatted_value}
                  </td>
                  <td className="px-2 py-1 text-center text-gray-500">
                    {item.year}
                  </td>
                  <td className="px-2 py-1">
                    <span
                      className="px-1.5 py-0.5 rounded text-white text-xs"
                      style={{
                        backgroundColor:
                          CATEGORY_COLORS[item.category] || CATEGORY_COLORS.other,
                      }}
                    >
                      {CATEGORY_LABELS[item.category] || item.category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
};

export default WorldBankChart;
