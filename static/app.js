fetch('/api/slots')
.then(r => r.json())
.then(data => {

 let html = '';

 data.forEach(x => {

   let cls = 'available';

   if(x[2] == 'Filling Fast') cls = 'progressing';
   if(x[2] == 'Full') cls = 'booked';

   html += `
   <div class="card ${cls}" onclick="book(${x[0]})">
      <h3>${x[1]}</h3>
      <p>${x[2]}</p>
      <small>${x[3]}</small>
   </div>
   `;
 });

 document.getElementById('slots').innerHTML = html;
});


function book(id){

 fetch('/api/book',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({slot_id:id})
 })

 .then(r => r.json())

 .then(d => {

    if(d.success){

        localStorage.setItem("userToken", d.token);

        alert(
          "Booking Confirmed!\n\n" +
          "Your Token: " + d.token +
          "\nSlot Time: " + d.time +
          "\n\nRedirecting to Queue Page..."
        );

        window.location.href = "/queue";

    }else{
        alert("Sorry! Slot Full. Please choose another.");
    }

 });

}