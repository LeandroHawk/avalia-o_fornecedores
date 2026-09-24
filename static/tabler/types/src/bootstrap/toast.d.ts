/**
 * --------------------------------------------------------------------------
 * Bootstrap toast.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import BaseComponent from './base-component';
import type { ComponentConfig, ComponentConfigType, ElementSelector } from './types';
declare class Toast extends BaseComponent {
    _timeout: ReturnType<typeof setTimeout> | null;
    _hasMouseInteraction: boolean;
    _hasKeyboardInteraction: boolean;
    constructor(element: ElementSelector, config?: ComponentConfig);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    show(): void;
    hide(): void;
    dispose(): void;
    isShown(): boolean;
    _maybeScheduleHide(): void;
    _onInteraction(event: Event, isInteracting: boolean): void;
    _setListeners(): void;
    _clearTimeout(): void;
}
export default Toast;
