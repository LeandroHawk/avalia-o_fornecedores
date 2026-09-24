/**
 * --------------------------------------------------------------------------
 * Bootstrap dom/event-handler.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
type EventCallback = (this: EventTarget, ...args: unknown[]) => void;
declare const EventHandler: {
    on(element: EventTarget | null, event: string, handler: string | EventCallback, delegationFunction?: EventCallback): void;
    one(element: EventTarget | null, event: string, handler: string | EventCallback, delegationFunction?: EventCallback): void;
    off(element: EventTarget | null, originalTypeEvent: string, handler?: string | EventCallback, delegationFunction?: EventCallback): void;
    trigger(element: EventTarget | null, event: string, args?: Record<string, unknown>): Event | null;
};
export default EventHandler;
