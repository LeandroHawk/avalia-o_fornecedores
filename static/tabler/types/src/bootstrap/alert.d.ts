/**
 * --------------------------------------------------------------------------
 * Bootstrap alert.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import BaseComponent from './base-component';
declare class Alert extends BaseComponent {
    static get NAME(): string;
    close(): void;
    _destroyElement(): void;
}
export default Alert;
