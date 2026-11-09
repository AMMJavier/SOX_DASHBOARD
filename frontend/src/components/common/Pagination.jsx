export default function Pagination({
    currentPage,
    totalPages,
    onPageChange
}) {

return (
<div className="flex justify-center gap-2 mt-6">

<button
disabled={currentPage===1}
onClick={()=>onPageChange(currentPage-1)}
>
‹
</button>


{
Array.from(
{length: totalPages},
(_,i)=>i+1
)
.map(page=>(

<button
key={page}
onClick={()=>onPageChange(page)}
className={
currentPage===page
?"bg-cyan-500 text-white px-4 py-2"
:"px-4 py-2"
}
>
{page}
</button>

))
}


<button
disabled={currentPage===totalPages}
onClick={()=>onPageChange(currentPage+1)}
>
›
</button>


</div>
)

}