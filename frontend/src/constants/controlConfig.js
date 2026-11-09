const controlConfig = {

    1:{
        id:"1",
        name:"Control 1 - Cambios en la SIS016",
        path:"/SOX/Controls/Control_1/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    },


    2:{
        id:"2",
        name:"Control 2 - Plan de Seguridad Ok de Gerencia",
        path:"/SOX/Controls/Control_2/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    },


    3:{
        id:"3",
        name:"Control 3 - Revisión del plan seguridades",
        path:"/SOX/Controls/Control_3/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    },


    4:{
        id:"4",
        name:"Control 4 - VPNs Corporativas",
        path:"/SOX/Controls/Control_4/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    },


    5:{
        id:"5",
        name:"Control 5 - Administradores del Firewall",
        path:"/SOX/Controls/Control_5/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    },


    6:{
        id:"6",
        name:"Control 6 - Personal Cesante vs VPN por eventos",
        path:"/SOX/Controls/Control_6/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    },


    7:{
        id:"7",
        name:"Control 7 - Evidencias VPN Internas y Externas",
        path:"/SOX/Controls/Control_7/dashboard",

        type:"campaign",

        hasCampaign:true,
        hasLogs:true,
        hasHistory:true,
        hasReports:true,
        hasStartProcess:true,

        period:"SEMESTRAL"
    },


    10:{
        id:"10",
        name:"Control 10 - Automatizado",
        path:"/SOX/Controls/Control_10/dashboard",

        type:"informative",

        hasCampaign:false,
        hasLogs:false,
        hasHistory:false,
        hasReports:false,
        hasStartProcess:false
    }

};


export default controlConfig;