import type { EventMap } from './types';

type Handler<T> = (payload: T) => void;

class EventBusImpl<T extends { [K in keyof T]: unknown }> {
    private handlers = new Map<keyof T, Set<Handler<unknown>>>();

    emit<K extends keyof T>(event: K, payload: T[K]): void {
        const set = this.handlers.get(event);
        if (!set) return;
        [...set].forEach((handler) => (handler as Handler<T[K]>)(payload));
    }

    on<K extends keyof T>(event: K, handler: Handler<T[K]>): () => void {
        if (!this.handlers.has(event)) {
            this.handlers.set(event, new Set());
        }
        this.handlers.get(event)!.add(handler as Handler<unknown>);
        // Returns unsubscribe function — MUST be called on component unmount
        return () => this.off(event, handler);
    }

    off<K extends keyof T>(event: K, handler: Handler<T[K]>): void {
        this.handlers.get(event)?.delete(handler as Handler<unknown>);
    }
}

// Singleton — tất cả frontend modules import từ đây
export const eventBus = new EventBusImpl<EventMap>();
