"use strict";

// Keep the classic-script global and synchronous registration used by existing pages.
(() => {
  let controller;
  window.LUMIERE_BACKEND_CONSOLE = async options => {
    try {
      controller ||= import("./pages/management-console.mjs")
        .then(module => module.createManagementConsole())
        .catch(error => { controller = null; throw error; });
      return await (await controller)(options);
    } catch (error) {
      const { showError } = await import("./shared/ui.mjs");
      showError(options.mount, error);
    }
  };
})();
