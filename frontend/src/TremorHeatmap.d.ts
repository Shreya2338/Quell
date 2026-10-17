import type { ComponentType } from "react";

type TremorSample = {
  day: number;
  hour: number;
  intensity: number;
};

type MedicationDose = {
  day: number;
  hour: number;
  label: string;
};

type TremorHeatmapProps = {
  samples?: TremorSample[];
  doses?: MedicationDose[];
  defaultHourStep?: number;
};

declare const TremorHeatmap: ComponentType<TremorHeatmapProps>;

export default TremorHeatmap;
