/**
 * ExportHistory — Story 3.3
 *
 * localStorage helper for tracking which sessions have been exported.
 * Key: "export_history"
 * Format: { "<filename>": { "date": "YYYY-MM-DD" }, ... }
 *
 * Design:
 * - localStorage is a UI cache only; backend is source of truth for duplicates.
 * - Corrupted JSON degrades gracefully (returns empty — no error thrown).
 * - Storage quota exceeded on write fails silently (non-critical feature).
 */

const STORAGE_KEY = 'export_history';

interface ExportRecord {
    date: string; // "YYYY-MM-DD"
}

type ExportHistoryMap = Record<string, ExportRecord>;

function _load(): ExportHistoryMap {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        // F1: reject arrays — typeof [] === 'object' passes the null check but is not a valid map
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) return parsed as ExportHistoryMap;
    } catch {
        // Corrupted localStorage — degrade gracefully
    }
    return {};
}

function _save(history: ExportHistoryMap): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch {
        // Storage quota exceeded — silently fail (non-critical feature)
    }
}

export const ExportHistory = {
    recordExport(filename: string, date: string): void {
        // F2: guard both blank filename and blank date
        if (!filename || !date) return;
        const history = _load();
        history[filename] = { date };
        _save(history);
    },

    getExportDate(filename: string): string | null {
        if (!filename) return null;
        const history = _load();
        return history[filename]?.date ?? null;
    },

    isExported(filename: string): boolean {
        return ExportHistory.getExportDate(filename) !== null;
    },

    getAllHistory(): ExportHistoryMap {
        return _load();
    },

    /** Format stored "YYYY-MM-DD" → display "DD/MM" */
    formatDisplayDate(isoDate: string): string {
        // F3: guard empty string — split('') gives [''] (length 1), return fallback
        if (!isoDate) return '??/??';
        const parts = isoDate.split('-');
        if (parts.length !== 3) return '??/??';
        const [, month, day] = parts;
        return `${day}/${month}`;
    },
};
