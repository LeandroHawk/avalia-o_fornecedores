/**
 * --------------------------------------------------------------------------
 * Bootstrap modal.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import BaseComponent from './base-component';
import Backdrop from './util/backdrop';
import FocusTrap from './util/focustrap';
import ScrollBarHelper from './util/scrollbar';
interface ComponentConfig {
    [key: string]: any;
}
interface ComponentConfigType {
    [key: string]: string;
}
/**
 * Class definition
 */
declare class Modal extends BaseComponent {
    _dialog: HTMLElement | null;
    _backdrop: Backdrop;
    _focustrap: FocusTrap;
    _isShown: boolean;
    _isTransitioning: boolean;
    _scrollBar: ScrollBarHelper;
    constructor(element: HTMLElement | string, config?: Partial<ComponentConfig>);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    toggle(relatedTarget?: HTMLElement): void;
    show(relatedTarget?: HTMLElement): void;
    hide(): void;
    dispose(): void;
    handleUpdate(): void;
    _initializeBackDrop(): Backdrop;
    _initializeFocusTrap(): FocusTrap;
    _showElement(relatedTarget?: HTMLElement): void;
    _addEventListeners(): void;
    _hideModal(): void;
    _isAnimated(): boolean;
    _triggerBackdropTransition(): void;
    _adjustDialog(): void;
    _resetAdjustments(): void;
}
export default Modal;
