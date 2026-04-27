/**
 * ResultsPanel — Phase 1 component
 * Manages CompletionOverlay and StatusBar display after replay.
 * Story 1.4: Phase 2 integration points added (Supabase button + Export link).
 */
import { sessionListPanel, isSupabaseEnabled } from './SessionListPanel';

export class ResultsPanel {
    private completionOverlay: HTMLElement | null = null;
    private statusBarEl: HTMLElement | null = null;
    private currentSessionFilename: string | null = null;

    constructor() {
        // Story 2.4: disable/enable Export buttons based on replay state
        document.addEventListener('exportpanel:canExport', (e: Event) => {
            const { canExport } = (e as CustomEvent<{ canExport: boolean }>).detail;
            // CompletionOverlay button (only rendered when Supabase enabled)
            const exportBtn = this.completionOverlay
                ?.querySelector<HTMLButtonElement>('.completion-export-btn');
            if (exportBtn) {
                exportBtn.disabled = !canExport;
                if (!canExport) {
                    exportBtn.setAttribute('aria-disabled', 'true');
                } else {
                    exportBtn.removeAttribute('aria-disabled');
                }
            }
            // StatusBar export link (span role="button" — use aria-disabled + tabindex for a11y)
            const exportLink = this.statusBarEl
                ?.querySelector<HTMLElement>('.statusbar-export-link');
            if (exportLink) {
                exportLink.style.pointerEvents = canExport ? 'auto' : 'none';
                exportLink.style.opacity = canExport ? '1' : '0.4';
                // G12: announce disabled state to screen readers and block keyboard activation
                if (!canExport) {
                    exportLink.setAttribute('aria-disabled', 'true');
                    exportLink.setAttribute('tabindex', '-1');
                } else {
                    exportLink.removeAttribute('aria-disabled');
                    exportLink.setAttribute('tabindex', '0');
                }
            }
        });
    }

    init(statusBarEl: HTMLElement): void {
        this.statusBarEl = statusBarEl;
    }

    // Called by ReplayEngine or main.ts when replay completes
    showCompletionOverlay(sessionFilename?: string): void {
        this.currentSessionFilename = sessionFilename ?? null;
        this.dismissCompletionOverlay();

        this.completionOverlay = document.createElement('div');
        this.completionOverlay.className = 'completion-overlay';
        this.completionOverlay.setAttribute('role', 'alertdialog');
        this.completionOverlay.setAttribute('aria-label', 'Replay hoàn thành');

        // Phase 2: conditionally show Supabase export button
        const supabaseButton = isSupabaseEnabled()
            ? `<button class="btn-primary completion-export-btn">📤 Lưu vào Supabase</button>`
            : '';

        this.completionOverlay.innerHTML = `
      <div class="completion-overlay-panel">
        <h3>✅ Replay hoàn thành</h3>
        <div class="completion-actions">
          <button class="btn-secondary completion-reset-btn">Reset</button>
          ${supabaseButton}
        </div>
      </div>
    `;

        // Phase 1: Reset button
        this.completionOverlay.querySelector('.completion-reset-btn')
            ?.addEventListener('click', () => {
                this.dismissCompletionOverlay();
                // Phase 1: notify reset (handled by main.ts / ReplayEngine)
                document.dispatchEvent(new CustomEvent('results:resetRequested'));
            });

        // Phase 2: Supabase export button (only rendered when supabase enabled)
        this.completionOverlay.querySelector('.completion-export-btn')
            ?.addEventListener('click', () => {
                this.dismissCompletionOverlay();
                sessionListPanel.open(this.currentSessionFilename ?? undefined);
            });

        document.body.appendChild(this.completionOverlay);

        // Update StatusBar to Complete mode
        this.renderStatusBarComplete();
    }

    dismissCompletionOverlay(): void {
        this.completionOverlay?.remove();
        this.completionOverlay = null;
    }

    // Phase 1 StatusBar update — shows replay state
    renderStatusBar(state: 'idle' | 'playing' | 'paused' | 'complete'): void {
        if (!this.statusBarEl) return;

        if (state === 'complete') {
            this.renderStatusBarComplete();
        } else {
            this.statusBarEl.innerHTML = `<span class="statusbar-state">${state}</span>`;
        }
    }

    private renderStatusBarComplete(): void {
        if (!this.statusBarEl) return;

        // Phase 2: export link only when Supabase enabled
        const exportLink = isSupabaseEnabled()
            ? `<span class="statusbar-export-link" role="button" tabindex="0">📤 Export</span>`
            : '';

        this.statusBarEl.innerHTML = `
      <span class="statusbar-state complete">✅ Hoàn thành</span>
      ${exportLink}
    `;

        // Phase 2: bind export link click
        this.statusBarEl.querySelector('.statusbar-export-link')
            ?.addEventListener('click', () => {
                sessionListPanel.open(this.currentSessionFilename ?? undefined);
            });
    }
}

export const resultsPanel = new ResultsPanel();
