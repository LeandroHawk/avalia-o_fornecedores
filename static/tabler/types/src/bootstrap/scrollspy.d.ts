/**
 * --------------------------------------------------------------------------
 * Bootstrap scrollspy.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import BaseComponent from './base-component';
import type { ComponentConfig, ComponentConfigType } from './types';
declare class ScrollSpy extends BaseComponent {
    _targetLinks: Map<string, HTMLElement>;
    _observableSections: Map<string, HTMLElement>;
    _rootElement: HTMLElement | null;
    _activeTarget: HTMLElement | null;
    _observer: IntersectionObserver | null;
    _previousScrollData: {
        visibleEntryTop: number;
        parentScrollTop: number;
    };
    constructor(element: HTMLElement | string, config?: Partial<ComponentConfig>);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    refresh(): void;
    dispose(): void;
    _configAfterMerge(config: ComponentConfig): ComponentConfig;
    _maybeEnableSmoothScroll(): void;
    _getNewObserver(): IntersectionObserver;
    _observerCallback(entries: IntersectionObserverEntry[]): void;
    _initializeTargetsAndObservables(): void;
    _process(target: HTMLElement): void;
    _activateParents(target: HTMLElement): void;
    _clearActiveClass(parent: HTMLElement): void;
}
export default ScrollSpy;
