function updateFlutedGlass() {
  document
    .querySelectorAll(".glass-container")
    .forEach((el) => {

      const width = el.offsetWidth;

      if (!width) return;

    //   const segments = Math.max(
    //     4,
    //     Math.round(width / 10)
    //   );
      const segments = 10;
      console.log("Segments:", segments);
      console.log("Width:", width); 

      el.setAttribute(
        "tlg-fluted-glass-segments",
        segments
      );
    });
}

window.addEventListener("load", updateFlutedGlass);
window.addEventListener("resize", updateFlutedGlass);