/**
 * --------------------------------------------------------------------------
 * Bootstrap tooltip.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import * as Popper from '@popperjs/core';
import BaseComponent from './base-component';
import TemplateFactory from './util/template-factory';
interface ComponentConfig {
    [key: string]: any;
}
interface ComponentConfigType {
    [key: string]: string;
}
/**
 * Class definition
 */
declare class Tooltip extends BaseComponent {
    _isEnabled: boolean;
    _timeout: ReturnType<typeof setTimeout> | number;
    _isHovered: boolean | null;
    _activeTrigger: Record<string, boolean>;
    _popper: Popper.Instance | null;
    _templateFactory: TemplateFactory | null;
    _newContent: Record<string, any> | null;
    tip: HTMLElement | null;
    _hideModalHandler: (() => void) | null;
    constructor(element: HTMLElement | string, config?: Partial<ComponentConfig>);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    enable(): void;
    disable(): void;
    toggleEnabled(): void;
    toggle(): void;
    dispose(): void;
    show(): void;
    hide(): void;
    update(): void;
    _isWithContent(): boolean;
    _getTipElement(): HTMLElement | null;
    _createTipElement(content: Record<string, any>): HTMLElement | null;
    setContent(content: Record<string, any>): void;
    _getTemplateFactory(content: Record<string, any>): TemplateFactory;
    _getContentForTemplate(): Record<string, any>;
    _getTitle(): string;
    _initializeOnDelegatedTarget(event: Event & {
        delegateTarget?: HTMLElement;
    }): Tooltip;
    _isAnimated(): boolean;
    _isShown(): boolean;
    _createPopper(tip: HTMLElement): Popper.Instance;
    _getOffset(): number[] | ((popperData: any) => number[]);
    _resolvePossibleFunction(arg: any): any;
    _getPopperConfig(attachment: string): Partial<Popper.Options>;
    _setListeners(): void;
    _fixTitle(): void;
    _enter(): void;
    _leave(): void;
    _setTimeout(handler: () => void, timeout: number): void;
    _isWithActiveTrigger(): boolean;
    _getConfig(config: Partial<ComponentConfig>): ComponentConfig;
    _configAfterMerge(config: ComponentConfig): ComponentConfig;
    _getDelegateConfig(): Partial<ComponentConfig>;
    _disposePopper(): void;
}
export default Tooltip;
