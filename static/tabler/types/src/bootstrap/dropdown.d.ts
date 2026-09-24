/**
 * --------------------------------------------------------------------------
 * Bootstrap dropdown.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import * as Popper from '@popperjs/core';
import BaseComponent from './base-component';
import type { ComponentConfig, ComponentConfigType } from './types';
declare class Dropdown extends BaseComponent {
    _popper: Popper.Instance | null;
    _parent: HTMLElement;
    _menu: HTMLElement;
    _inNavbar: boolean;
    constructor(element: HTMLElement | string, config?: Partial<ComponentConfig>);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    toggle(): void;
    show(): void;
    hide(): void;
    dispose(): void;
    update(): void;
    _completeHide(relatedTarget: Record<string, any>): void;
    _getConfig(config: Partial<ComponentConfig>): ComponentConfig;
    _createPopper(): void;
    _isShown(): boolean;
    _getPlacement(): string;
    _detectNavbar(): boolean;
    _getOffset(): number[] | ((popperData: any) => number[]);
    _getPopperConfig(): Partial<Popper.Options>;
    _selectMenuItem({ key, target }: {
        key: string;
        target: HTMLElement;
    }): void;
    static clearMenus(event: Event & {
        button?: number;
        key?: string;
        composedPath?: () => EventTarget[];
    }): void;
    static dataApiKeydownHandler(this: HTMLElement, event: KeyboardEvent): void;
}
export default Dropdown;
