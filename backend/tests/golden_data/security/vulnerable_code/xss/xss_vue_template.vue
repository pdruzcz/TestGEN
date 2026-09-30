<!-- Golden security fixture (Story 4.14) — Vue XSS via v-html (CWE-79). -->
<!-- Intentionally vulnerable reference sample for scanner regression tests. -->
<template>
  <div v-html="userContent"></div>
</template>
