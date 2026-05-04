import type { ISeriesApi } from 'lightweight-charts';

export class CoordinateTranslator {
  private series: ISeriesApi<'Candlestick'> | null = null;
  isUpdating = false;   // public — DrawingManager reads to prevent event loops

  init(series: ISeriesApi<'Candlestick'>): void {
    this.series = series;
  }

  isInitialized(): boolean {
    return this.series !== null;
  }

  priceToY(price: number): number | null {
    if (!this.series) return null;
    const coord = this.series.priceToCoordinate(price);
    return coord ?? null;
  }

  yToPrice(y: number): number | null {
    if (!this.series) return null;
    const price = this.series.coordinateToPrice(y);
    return price ?? null;
  }
}
