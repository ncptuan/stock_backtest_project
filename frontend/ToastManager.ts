export type ToastType = 'info' | 'warning' | 'error';

export interface ToastOptions {
  duration?: number;
  undoDuration?: number;
  onUndo?: () => void;
}

class ToastManagerImpl {
  private container: HTMLElement | null = null;
  private count = 0;
  private activeToasts: HTMLElement[] = [];

  private getContainer(): HTMLElement {
    if (!this.container) {
      this.container = document.getElementById('toast-root');
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.id = 'toast-root';
        document.body.appendChild(this.container);
      }
    }
    return this.container;
  }

  show(message: string, type: ToastType = 'info', opts: ToastOptions = {}): void {
    const container = this.getContainer();

    // Max 3 toasts — remove oldest
    if (this.count >= 3) {
      const oldest = container.querySelector('.toast');
      if (oldest) oldest.remove();
      this.count--;
    }

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    this.count++;

    let dismissed = false;
    const dismiss = (): void => {
      if (dismissed) return;
      dismissed = true;
      toast.classList.add('toast--hiding');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.remove();
          this.count = Math.max(0, this.count - 1);
        }
        this.activeToasts = this.activeToasts.filter(t => t !== toast);
      }, 200);
    };

    if (opts.undoDuration && opts.onUndo) {
      let remaining = Math.ceil(opts.undoDuration / 1000);
      let undoTriggered = false;

      const countdownSpan = document.createElement('span');
      countdownSpan.className = 'toast-countdown';
      countdownSpan.textContent = `(${remaining}s)`;

      const undoBtn = document.createElement('button');
      undoBtn.className = 'toast-undo-btn';
      undoBtn.textContent = 'Hoàn tác';
      undoBtn.addEventListener('click', () => {
        undoTriggered = true;
        opts.onUndo!();
        clearInterval(timer);
        dismiss();
      });

      const msgSpan = document.createElement('span');
      msgSpan.className = 'toast-msg';
      msgSpan.textContent = message;
      toast.appendChild(msgSpan);
      toast.appendChild(countdownSpan);
      toast.appendChild(undoBtn);

      const timer = setInterval(() => {
        remaining--;
        countdownSpan.textContent = `(${remaining}s)`;
        if (remaining <= 0) {
          clearInterval(timer);
          if (!undoTriggered) dismiss();
        }
      }, 1000);

      const fallbackTimer = setTimeout(() => {
        if (!undoTriggered) dismiss();
      }, opts.undoDuration);

      // Store timer IDs so dismiss() can clear them
      toast.dataset.timerId = String(timer);
      toast.dataset.fallbackTimerId = String(fallbackTimer);
    } else {
      const msgSpan = document.createElement('span');
      msgSpan.className = 'toast-msg';
      msgSpan.textContent = message;
      toast.appendChild(msgSpan);
      const duration = opts.duration ?? 4000;
      setTimeout(dismiss, duration);
    }

    container.appendChild(toast);
    this.activeToasts.push(toast);
  }

  dismiss(): void {
    for (const toast of this.activeToasts) {
      // Cancel undo timers to prevent leaks
      const timerId = toast.dataset.timerId;
      const fallbackTimerId = toast.dataset.fallbackTimerId;
      if (timerId) clearInterval(Number(timerId));
      if (fallbackTimerId) clearTimeout(Number(fallbackTimerId));

      toast.classList.add('toast--hiding');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.remove();
          this.count = Math.max(0, this.count - 1);
        }
      }, 200);
    }
    this.activeToasts = [];
  }
}

export const toastManager = new ToastManagerImpl();
