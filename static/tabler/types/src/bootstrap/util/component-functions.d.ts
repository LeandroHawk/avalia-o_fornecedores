/**
 * --------------------------------------------------------------------------
 * Bootstrap util/component-functions.ts
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)
 * --------------------------------------------------------------------------
 */
interface DismissibleComponent {
    EVENT_KEY: string;
    NAME: string;
    getOrCreateInstance(element: HTMLElement | string | null): any;
}
declare const enableDismissTrigger: (component: DismissibleComponent, method?: string) => void;
export { enableDismissTrigger };
