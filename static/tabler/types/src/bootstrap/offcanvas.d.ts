/**
 * --------------------------------------------------------------------------
 * Bootstrap offcanvas.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import BaseComponent from './base-component';
import Backdrop from './util/backdrop';
import FocusTrap from './util/focustrap';
interface ComponentConfig {
    [key: string]: any;
}
interface ComponentConfigType {
    [key: string]: string;
}
/**
 * Class definition
 */
declare class Offcanvas extends BaseComponent {
    _isShown: boolean;
    _backdrop: Backdrop;
    _focustrap: FocusTrap;
    constructor(element: HTMLElement | string, config?: Partial<ComponentConfig>);
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    toggle(relatedTarget?: HTMLElement): void;
    show(relatedTarget?: HTMLElement): void;
    hide(): void;
    dispose(): void;
    _initializeBackDrop(): Backdrop;
    _initializeFocusTrap(): FocusTrap;
    _addEventListeners(): void;
}
export default Offcanvas;
