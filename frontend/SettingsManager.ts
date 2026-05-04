import type { PersistedSettings } from './types';

const STORAGE_KEY = 'btcReplay_lastSettings';

function getDefaultDateRange(): { dateStart: string; dateEnd: string } {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 6);
  const fmt = (d: Date): string => d.toISOString().slice(0, 10);
  return { dateStart: fmt(start), dateEnd: fmt(end) };
}

export class SettingsManager {
  private saveTimeout: number | null = null;

  load(): PersistedSettings {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return this.getDefaults();
      const parsed = JSON.parse(raw) as Partial<PersistedSettings>;
      if (!parsed.timeframe || !parsed.dateStart || !parsed.dateEnd) {
        return this.getDefaults();
      }
      return {
        timeframe: parsed.timeframe,
        dateStart: parsed.dateStart,
        dateEnd: parsed.dateEnd,
        drawings: parsed.drawings,
      };
    } catch {
      return this.getDefaults();
    }
  }

  save(settings: PersistedSettings): void {
    if (this.saveTimeout) clearTimeout(this.saveTimeout);
    this.saveTimeout = window.setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        console.warn(`[SettingsManager] save failed: ${msg}`);
      }
    }, 500);
  }

  getDefaults(): PersistedSettings {
    const { dateStart, dateEnd } = getDefaultDateRange();
    return { timeframe: '4h', dateStart, dateEnd };
  }
}

export const settingsManager = new SettingsManager();
