function escapeHtml(s: string): string {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

export class QualityGateBlock {
    private overlay: HTMLElement | null = null;

    open(reason: string): void {
        // P13: defensive remove before add prevents stale listeners on double-open
        document.removeEventListener('keydown', this.handleKeyDown);
        this.render(reason);
        document.addEventListener('keydown', this.handleKeyDown);
    }

    close(): void {
        this.overlay?.remove();
        this.overlay = null;
        document.removeEventListener('keydown', this.handleKeyDown);
    }

    private render(reason: string): void {
        this.overlay?.remove();

        // reason may contain semicolon-separated items:
        // "7 trades — cần tối thiểu 10; 48% win rate — cần tối thiểu 55%"
        const reasons = reason.split(';').map((r) => r.trim()).filter(Boolean);

        this.overlay = document.createElement('div');
        this.overlay.className = 'quality-gate-overlay';

        this.overlay.innerHTML = `
      <div class="quality-gate-modal" role="alertdialog" aria-modal="true"
           aria-describedby="quality-gate-explanation">
        <div class="quality-gate-icon">⚠️</div>
        <h2 class="quality-gate-title">Session chưa đủ điều kiện export</h2>
        <div class="quality-gate-reasons">
          ${reasons.map((r) => `<div class="quality-gate-reason">❌ ${escapeHtml(r)}</div>`).join('')}
        </div>
        <p class="quality-gate-explanation" id="quality-gate-explanation">
          Sample nhỏ có thể cho kết quả ngẫu nhiên. Bot học tốt hơn từ sessions có đủ data.
        </p>
        <div class="quality-gate-footer">
          <button class="btn-primary quality-gate-close-btn">Đóng</button>
        </div>
      </div>
    `;

        // Backdrop click closes
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) this.close();
        });

        this.overlay.querySelector('.quality-gate-close-btn')!
            .addEventListener('click', () => this.close());

        document.body.appendChild(this.overlay);

        // Focus Đóng button (accessibility: alertdialog must focus first interactive)
        (this.overlay.querySelector('.quality-gate-close-btn') as HTMLElement)?.focus();
    }

    private handleKeyDown = (e: KeyboardEvent): void => {
        if (e.key === 'Escape') {
            e.preventDefault();
            this.close();
        }
    };
}

export const qualityGateBlock = new QualityGateBlock();
