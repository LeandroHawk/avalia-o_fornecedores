/**
 * --------------------------------------------------------------------------
 * Bootstrap collapse.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import BaseComponent from './base-component';
import type { ComponentConfig, ComponentConfigType, ElementSelector } from './types';
declare const WIDTH = "width";
declare const HEIGHT = "height";
declare class Collapse extends BaseComponent {
    _isTransitioning: boolean;
    _triggerArray: HTMLElement[];
    constructor(element: ElementSelector, config?: ComponentConfig);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    toggle(): void;
    show(): void;
    hide(): void;
    _isShown(element?: HTMLElement): boolean;
    _configAfterMerge(config: ComponentConfig): ComponentConfig;
    _getDimension(): typeof WIDTH | typeof HEIGHT;
    _initializeChildren(): void;
    _getFirstLevelChildren(selector: string): HTMLElement[];
    _addAriaAndCollapsedClass(triggerArray: HTMLElement[], isOpen: boolean): void;
}
export default Collapse;
