/* A native-scroll reading cue for the gateway's three legs. The parent's
 * untransformed geometry avoids feedback with the existing reveal animation.
 * One demand-driven RAF; no timers, loop at rest, scroll trap or network. */
(function () {
  'use strict';
  const grid=document.querySelector('[data-route-grid]');
  if(!grid)return;
  const nodes=Array.from(grid.children);
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const narrow=matchMedia('(max-width: 760px)');
  let visible=false, raf=0, progress=0;
  function schedule(){if(!reduce.matches&&visible&&!document.hidden&&!raf)raf=requestAnimationFrame(paintRoute);}
  function paintRoute(){
    raf=0;if(reduce.matches||!visible||document.hidden)return;
    const r=grid.getBoundingClientRect(),vh=Math.max(1,innerHeight);
    const target=Math.max(0,Math.min(1,narrow.matches?(vh*.65-r.top)/Math.max(1,r.height):(vh*.9-r.top)/(vh*.65)));
    progress+=(target-progress)*.18;
    if(Math.abs(target-progress)<.002)progress=target;
    grid.style.setProperty('--route-progress',progress.toFixed(4));
    const current=Math.min(nodes.length-1,Math.floor(progress*nodes.length));
    nodes.forEach((node,i)=>{node.classList.toggle('is-route-current',i===current);node.classList.toggle('is-route-done',i<current);});
    if(progress!==target)schedule();
  }
  function configure(){
    cancelAnimationFrame(raf);raf=0;
    if(reduce.matches){grid.style.removeProperty('--route-progress');nodes.forEach(node=>node.classList.remove('is-route-current','is-route-done'));}
    else schedule();
  }
  if('IntersectionObserver' in window){new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(!visible){cancelAnimationFrame(raf);raf=0;}else schedule();},{rootMargin:'80px 0px'}).observe(grid);}
  else visible=true;
  addEventListener('scroll',schedule,{passive:true});addEventListener('resize',schedule,{passive:true});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;}else schedule();});
  addEventListener('pagehide',()=>{cancelAnimationFrame(raf);raf=0;});addEventListener('pageshow',schedule);
  reduce.addEventListener('change',configure);narrow.addEventListener('change',schedule);configure();
}());
