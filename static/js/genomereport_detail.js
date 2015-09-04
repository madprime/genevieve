function guessGETEvidenceID (clinvarName) {
  var reFS = /\((.*?)\):.*?\(p\.(.*?[0-9]+)[A-Z][a-z][a-z]fs\)/
  var matchFS = reFS.exec(clinvarName)
  var reAASub = /\((.*?)\):.*?\(p\.([A-Za-z]+[0-9]+[A-Za-z]+)\)/
  var matchAASub = reAASub.exec(clinvarName)
  if (matchFS !== null) {
    return matchFS[1] + '-' + matchFS[2] + 'Shift'
  } else if (matchAASub !== null) {
    return matchAASub[1] + '-' + matchAASub[2].replace('Ter', 'Stop')
  }
  return ''
}

function parseB37ID (b37ID) {
  var parsed = {}
  var reB37ID = /([0-9]{1,2})-([0-9]+)-([ACGT]+)-([ACGT]+)/
  var matchB37ID = reB37ID.exec(b37ID)
  if (matchB37ID != null) {
    parsed.chrom = matchB37ID[1]
    parsed.pos = matchB37ID[2]
    parsed.refAllele = matchB37ID[3]
    parsed.varAllele = matchB37ID[4]
    if (parsed.chrom === '23') {
      parsed.chrom = 'X'
    } else if (parsed.chrom === '24') {
      parsed.chrom = 'Y'
    } else if (parsed.chrom === '25') {
      parsed.chrom = 'M'
    }
    return parsed
  }
  return null
}

function addIdData (parsedVar, clinvarRelationsData, template, elem) {
  var varNameString = ''
  var varNames = []

  // Get preferred name(s) from ClinVar data.
  clinvarRelationsData.forEach(function (clinvarData) {
    var prefName = clinvarData['clinvar-rcva:preferred-name']
    if (!prefName) return
    if (varNameString) {
      // If this name already listed, don't output again.
      if (_.contains(varNames, prefName)) return
      varNameString = varNameString + '</b><br><small>or</small><br><b>' +
                      prefName
    } else {
      varNameString = clinvarData['clinvar-rcva:preferred-name']
    }
    varNames.push(prefName)
  })

  // Put together a position + change description.
  var b37VariantID = 'Chr' + parsedVar.chrom + ': ' + parsedVar.pos + ' ' +
    parsedVar.refAllele + ' > ' + parsedVar.varAllele

  // Guess the GET-Evidence link
  var getevID = guessGETEvidenceID(clinvarRelationsData[0]['clinvar-rcva:preferred-name'])
  var getevLink = 'http://evidence.pgp-hms.org/' + getevID

  var templated = template({
    clinvarRCVAPreferredName: varNameString,
    b37VariantID: b37VariantID,
    linkGETEvidence: getevLink
  })
  elem.append(templated)
  return [clinvarRelationsData[0]['clinvar-rcva:preferred-name'], b37VariantID, getevLink]
}

function addFreqData (parsedVar, clinvarRelationsData, template, elem) {
  var frequencies = []
  var freq
  clinvarRelationsData.forEach(function (clinvarData) {
    if ('genevieve:allele-frequency' in clinvarData) {
      freq = clinvarData['genevieve:allele-frequency']
      frequencies.push(freq)
      return
    }
    if ('clinvar-rcva:esp-allele-frequency' in clinvarData) {
      freq = clinvarData['clinvar-rcva:esp-allele-frequency']
      frequencies.push(freq)
    }
  })
  // console.log(frequencies)
  var frequency
  if (frequencies.length === 0) {
    frequency = 'Unknown'
  } else {
    frequency = frequencies[0].substr(0, 9)
  }
  var linkExAC = 'http://exac.broadinstitute.org/variant/' + parsedVar.chrom +
    '-' + parsedVar.pos + '-' + parsedVar.refAllele + '-' + parsedVar.varAllele
  var templated = template({
    clinvarRCVAfreqESP: frequency,
    linkExAC: linkExAC
  })
  elem.append(templated)
  // console.log(elem)
  return [frequency, linkExAC]
}

function addInfoData (clinvarRelationsData, template, elem) {
  var variantID = elem.attr('id')
  var returnData = []
  clinvarRelationsData.forEach(function (clinvarData) {
    var traitType = clinvarData['clinvar-rcva:trait-type']
    var traitLabel
    if (traitType === 'Disease') {
      traitLabel = 'Disease'
    } else {
      traitLabel = 'Trait'
    }
    var templated = template({
      clinvarTraitLabel: traitLabel,
      clinvarRCVAAccession: clinvarData['clinvar-rcva:accession'],
      clinvarRCVADiseaseName: clinvarData['clinvar-rcva:trait-name'],
      clinvarRCVASignificance: clinvarData['clinvar-rcva:significance'],
      genevieveInheritance: clinvarData['genevieve:inheritance'],
      genevieveEvidence: clinvarData['genevieve:evidence'],
      genevieveNotes: clinvarData['genevieve:notes'],
      localVariantID: variantID
    })
    // console.log(templated)
    elem.append(templated)
    var noGenevieveData = (!(clinvarData['genevieve:inheritance'] ||
                              clinvarData['genevieve:evidence'] ||
                              clinvarData['genevieve:notes']))
    if (noGenevieveData) {
      var elemListGenevieve = elem.find('ul.genevieve-information').empty()
      elemListGenevieve.append('<li>No Genevieve notes.</li>')
    }
    returnData.push([
      traitLabel,
      clinvarData['clinvar-rcva:accession'],
      clinvarData['clinvar-rcva:trait-name'],
      clinvarData['clinvar-rcva:significance'],
      clinvarData['genevieve:inheritance'],
      clinvarData['genevieve:evidence'],
      clinvarData['genevieve:notes']
    ])
  })
  // console.log(elem)
  return returnData
}

function asCSVContent (idData, freqData, infoData) {
  var csvContent = ''
  infoData.forEach(function (infoDataItem) {
    var data = idData.concat(freqData).concat(infoDataItem).map(function (e) {
      return '"' + e + '"'
    })
    csvContent += data.join(',') + '\n'
  })
  return csvContent
}

function addGennotesData (data, textStatus, jqXHR) {
  // While processing, we also build a CSV version of the data for download.
  var csvContent = ''

  data['results'].forEach(function (result) {
    // Set up target elements and empty them.
    var rowGV = $('tr#gv-' + result['b37_id'])
    var elemGVID = rowGV.find('td.gv-id-cell').empty()
    var elemGVFreq = rowGV.find('td.gv-freq-cell').empty()
    var elemGVInfo = rowGV.find('td.gv-info-cell').empty()

    // Load appropriate templates.
    var templateVariantID = _.template($('#variant-id-template').html())
    var templateVariantFreq = _.template($('#variant-freq-template').html())
    var templateVariantInfo = _.template($('#variant-info-template').html())

    // Get all Relations of type 'clinvar-rcva'. These are the associated
    // ClinVar assertions, and may also contain Genevieve notes.
    var clinvarRelationsData = []
    result['relation_set'].forEach(function (relation) {
      if (relation['tags']['type'] === 'clinvar-rcva') {
        clinvarRelationsData.push(relation['tags'])
      }
    })

    // No Relations in GenNotes! Skip. This can happen when the ClinVar record
    // is applies to multiple variants in combination. GenNotes doesn't store
    // records for those cases.
    if (clinvarRelationsData.length === 0) {
      rowGV.addClass('hidden')
      return
    }

    // Get parsed variant info: [chrom, pos, varAllele, refAllele]
    parsedVar = parseB37ID(result['b37_id'])

    // Add data to each of these templates. Returned data is used for the CSV.
    var idData = addIdData(parsedVar, clinvarRelationsData, templateVariantID, elemGVID)
    var freqData = addFreqData(parsedVar, clinvarRelationsData, templateVariantFreq, elemGVFreq)
    var infoData = addInfoData(clinvarRelationsData, templateVariantInfo, elemGVInfo)
    csvContent += asCSVContent(idData, freqData, infoData)
  })

  // Add CSV download link.
  var downloadCSVDiv = $('div#download-as-csv').empty()
  var filenameCSV = $('#report-name').text() + '.csv'
  var downloadCSVLink = $('<a>Download as CSV file</a>')
    .attr('href', 'data:text/csv;charset=utf8,' + encodeURIComponent(csvContent))
    .attr('download', filenameCSV)
  downloadCSVDiv.append(downloadCSVLink)

  // Sort the table according to allele frequency.
  var elem = $('table#genome-report')
  elem.tablesorter({
    headers:
      {
        1: { sorter: 'digit' }
      },
    sortList: [[1, 0]]
  })
}

$(function () {
  // Collect list of all variants, defined by the id attribute of the rows.
  var variantList = $('tr.gv-row').map(function () {
    return $(this).attr('id').substring(3)
  }).toArray()

  // Fetch GenNotes data for this list, then run addGennotesData with it.
  var variantListJSON = JSON.stringify(variantList)
  $.ajax({
    url: 'https://gennotes.herokuapp.com/api/variant/',
    dataType: 'json',
    data: {'variant_list': variantListJSON, 'page_size': 100},
    success: addGennotesData,
    error: function (jqXHR, err) {
      console.log('Error in AJAX call to GenNotes: ' + err)
    }
  })
})
