/**
 * --------------------------------------------------------------------------
 * Bootstrap popover.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
import Tooltip from './tooltip';
interface ComponentConfig {
    [key: string]: any;
}
interface ComponentConfigType {
    [key: string]: string;
}
/**
 * Class definition
 */
declare class Popover extends Tooltip {
    static get Default(): ComponentConfig;
    static get DefaultType(): ComponentConfigType;
    static get NAME(): string;
    _isWithContent(): boolean;
    _getContentForTemplate(): Record<string, any>;
    _getContent(): any;
}
export default Popover;
