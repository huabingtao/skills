() => {
  const originals = [...document.querySelectorAll('section.card')];
  const errors = [], counts = [];
  const bottomLimit = card => card.querySelector('.footer-note,.brand').getBoundingClientRect().top - 6;
  const fits = card => {
    const b = card.getBoundingClientRect();
    return [...card.querySelector('.body').children].filter(n => !n.matches('.brand,.footer-note'))
      .every(n => {const r=n.getBoundingClientRect();return r.bottom<=bottomLimit(card)&&r.right<=b.right&&r.left>=b.left;});
  };
  // Split a rich paragraph with DOM ranges, retaining markup and atomic item spans.
  function splitParagraph(node, count) {
    const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let n,pos=0;
    while((n=walker.nextNode())) {
      if(pos+n.length>=count) {
        let offset=count-pos,atomic=n.parentElement.closest('.item-inline,.keep-together');
        if(atomic&&node.contains(atomic)) {
          const before=document.createRange();before.selectNodeContents(node);before.setEndBefore(atomic);
          count=before.toString().length;
          if(!count)return null;
          return splitParagraphOutside(node,atomic);
        }
        if(offset>0 && offset<n.length && /[\uD800-\uDBFF]/.test(n.data[offset-1]) && /[\uDC00-\uDFFF]/.test(n.data[offset]))offset--;
        const a=document.createRange(),z=document.createRange();
        a.selectNodeContents(node);a.setEnd(n,offset);z.selectNodeContents(node);z.setStart(n,offset);
        const left=node.cloneNode(false),right=node.cloneNode(false);left.append(a.cloneContents());right.append(z.cloneContents());
        return [left,right];
      }
      pos+=n.length;
    }
    return null;
  }
  function splitParagraphOutside(node,atomic) {
    const a=document.createRange(),z=document.createRange();a.selectNodeContents(node);a.setEndBefore(atomic);
    z.selectNodeContents(node);z.setStartBefore(atomic);
    const left=node.cloneNode(false),right=node.cloneNode(false);left.append(a.cloneContents());right.append(z.cloneContents());return [left,right];
  }
  originals.forEach((original,origin) => {
    const body=original.querySelector('.body'), footer=body?.querySelector(':scope > .brand');
    if(!body||!footer){errors.push(`第${origin+1}页缺少.body或.brand`);return;}
    original.dataset.origin=origin;
    if(fits(original)){counts.push(1);return;}
    if(original.dataset.kind==='cover'){errors.push('封面内容溢出，请精简封面');return;}
    const nodes=[...body.children].filter(n=>!n.matches('.brand,.footer-note'));
    const headers=[];
    while(nodes.length && nodes[0].matches('.eyebrow,.target,h1,h2'))headers.push(nodes.shift());
    const footnote=body.querySelector(':scope > .footer-note');
    const units=[];
    nodes.forEach((n,g) => {
      if(n.matches('table')) {
        [...n.querySelectorAll('tbody > tr')].forEach(row=>units.push({node:row,wrapper:n,group:g,kind:'table'}));
      } else if(n.matches('.reward-list,ul,ol')&&n.children.length) {
        [...n.children].forEach(row=>units.push({node:row,wrapper:n,group:g,kind:'list'}));
      } else units.push({node:n,group:g});
    });
    let pageNo=0,card,currentBody,contentCount=0;
    function newPage() {
      const next=original.cloneNode(false);next.dataset.origin=origin;
      currentBody=body.cloneNode(false);next.append(currentBody);
      headers.forEach(h=>currentBody.append(h.cloneNode(true)));
      if(pageNo) {
        const label=currentBody.querySelector('.eyebrow');
        if(label)label.append(` · 续${pageNo}`);
      }
      if(footnote)currentBody.append(footnote.cloneNode(true));
      currentBody.append(footer.cloneNode(true));
      if(card)card.after(next);else original.before(next);
      card=next;pageNo++;contentCount=0;
    }
    function append(unit) {
      const node=unit.node.cloneNode(true);let container,created=false;
      if(unit.wrapper) {
        container=[...currentBody.children].find(n=>n.dataset.flowContainer===String(unit.group))||null;
        if(!container) {
          container=unit.wrapper.cloneNode(false);container.dataset.flowContainer=unit.group;
          if(unit.kind==='table') {
            const head=unit.wrapper.querySelector('thead');if(head)container.append(head.cloneNode(true));
            container.append(document.createElement('tbody'));
          }
          currentBody.insertBefore(container,currentBody.querySelector('.footer-note,.brand'));created=true;
        }
        (unit.kind==='table'?container.querySelector('tbody'):container).append(node);
      } else currentBody.insertBefore(node,currentBody.querySelector('.footer-note,.brand'));
      return {node,undo:()=>{node.remove();if(created)container.remove();}};
    }
    newPage();let guard=0;
    while(units.length&&guard++<10000) {
      const unit=units.shift(),added=append(unit);
      if(fits(card)) {contentCount++;continue;}
      added.undo();
      const last=[...currentBody.children].filter(n=>!n.matches('.brand,.footer-note')).at(-1);
      if(contentCount && !(contentCount===1 && last?.matches('h3'))) {
        // Keep a section heading with the following row/paragraph.
        if(last?.matches('h3')&&!headers.includes(last)){last.remove();units.unshift(unit);units.unshift({node:last,group:'heading'});}else units.unshift(unit);
        newPage();continue;
      }
      if(unit.node.matches('p:not(.keep-together)')&&unit.node.textContent.length>1) {
        let lo=1,hi=unit.node.textContent.length-1,best=null;
        while(lo<=hi) {
          const mid=Math.floor((lo+hi)/2),parts=splitParagraph(unit.node,mid);
          if(!parts){hi=mid-1;continue;}
          const trial=append({...unit,node:parts[0]});const ok=fits(card);trial.undo();
          if(ok){best=parts;lo=mid+1;}else hi=mid-1;
        }
        if(best&&best[0].textContent.length&&best[1].textContent.length) {
          append({...unit,node:best[0]});units.unshift({...unit,node:best[1]});newPage();continue;
        }
      }
      errors.push(`原第${origin+1}页有无法完整容纳的${unit.node.tagName}，请调整内容或拆分；不缩小字号。`);break;
    }
    if(guard>=10000)errors.push('分页次数异常');
    original.remove();counts.push(pageNo);
  });
  const cards=[...document.querySelectorAll('section.card')];
  cards.forEach((card,i)=>{
    const label=card.querySelector('.brand span');if(label){const base=label.textContent.replace(/\s*\d+\s*\/\s*\d+\s*$/,'').trim();label.textContent=`${base}　${String(i+1).padStart(2,'0')} / ${String(cards.length).padStart(2,'0')}`;}
  });
  return {errors,pages_per_input:counts};
}
